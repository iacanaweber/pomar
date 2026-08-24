"""Rota central: gera o plano de aporte do dia.

O plano é um REBALANCEAMENTO: o usuário marca as classes que quer aportar, informa o
valor disponível, e o Pomar responde quanto comprar de cada ativo da carteira alvo para
chegar mais perto dos pesos que ele mesmo definiu. Ativos abaixo do preço-teto de Bazin
vêm marcados mesmo sem compra sugerida — antecipar é decisão do usuário, não do app.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.deps import get_brapi, get_cache, get_db, get_ghostfolio, get_sgs
from app.models.plan import (
    ALLOCATION_CLASSES,
    CLASS_LABEL,
    INVESTABLE_CLASSES,
    RENDA_FIXA,
    PlanAsset,
    PlanRequest,
    PlanResponse,
    PlanSummary,
    ReserveSuggestion,
)
from app.models.portfolio import Allocations, Portfolio
from app.repositories import fixed_income_repo, labels_repo, plans_repo, preferences_repo
from app.services import reserve as reserve_svc
from app.services.allocation import allocate
from app.services.analysis import analyze_asset, resolve_bazin_target_yield
from app.services.portfolio_service import get_enriched_portfolio
from app.services.reserve_service import resolve_floor
from app.services.universe import build_universe

router = APIRouter()


# Diferença mínima (em pontos percentuais) para dizer que o ativo está "abaixo do alvo".
GAP_PP_MIN = 0.5


def _plan_reasons(item: PlanAsset, classes_at_target: set[str]) -> list[str]:
    """Frases factuais: por que este ativo recebeu (ou não) compra neste plano.

    `classes_at_target` são as classes que já estão no/acima do peso-alvo — nelas nenhum
    ativo recebe aporte, por mais atrasado que esteja DENTRO da cesta. Dizer isso é o que
    evita a contradição de anunciar "50 p.p. abaixo do alvo" logo acima de "sem compra".
    """
    out: list[str] = []
    label = CLASS_LABEL.get(item.asset_class, item.asset_class)
    gap_pp = None
    if item.basket_target_pct is not None and item.basket_current_pct is not None:
        gap_pp = (item.basket_target_pct - item.basket_current_pct) * 100
        if gap_pp >= GAP_PP_MIN:
            out.append(f"Está {gap_pp:.1f} p.p. abaixo do alvo na cesta de {label}")
    if item.bazin_below_ceiling and item.bazin_margin:
        out.append(f"Desconto de {item.bazin_margin * 100:.0f}% sobre o preço-teto de Bazin")
    if item.suggested is None:
        if item.asset_class in classes_at_target:
            out.append(
                f"{label} já está no peso-alvo da carteira — o aporte foi para as classes "
                "mais atrasadas"
            )
        elif gap_pp is not None and gap_pp >= GAP_PP_MIN:
            out.append(
                "Não coube neste aporte (ticket mínimo ou lote) — quem estava mais atrasado "
                "levou primeiro"
            )
        else:
            out.append("No alvo ou acima do peso-alvo — sem compra sugerida")
    return out


@router.post("/plan", response_model=PlanResponse)
async def plan(req: PlanRequest) -> PlanResponse:
    settings = get_settings()
    warnings: list[str] = []

    # 1) carteira atual — FAIL-CLOSED por padrão: sem carteira (nem cache stale), um plano
    # ignoraria as posições existentes e miraria os alvos do zero — sugestão materialmente
    # errada para dinheiro de verdade. Só degrada com opt-in explícito do usuário.
    try:
        overrides = await labels_repo.bucket_overrides(get_db())
        portfolio = await get_enriched_portfolio(get_ghostfolio(), get_cache(), overrides)
        warnings.extend(portfolio.warnings)
    except Exception as exc:  # noqa: BLE001
        if not req.allow_empty_portfolio:
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Não consegui ler sua carteira no Ghostfolio ({exc}) e não há cópia em "
                    "cache. Plano abortado para não sugerir compras erradas — tente de novo "
                    "ou, se quiser mesmo planejar do zero, use 'planejar sem a carteira'."
                ),
            )
        warnings.append(
            f"Não consegui ler o Ghostfolio ({exc}); seguindo com carteira VAZIA a seu pedido. "
            "O rebalanceamento vai mirar diretamente os alvos e ignora posições existentes."
        )
        portfolio = Portfolio(
            total_value=0.0, as_of=datetime.now(timezone.utc).isoformat(),
            allocations=Allocations(),
        )

    prefs = await preferences_repo.get(get_db(), settings)
    # As metas por classe vêm das preferências (a UI as edita na Carteira alvo); o request
    # só as sobrepõe quando manda explicitamente. Cair direto no default do Settings fazia
    # o plano dividir o dinheiro por uma meta que o usuário nunca escolheu.
    targets = req.targets or prefs.get("targets") or settings.default_targets

    # 2) classes marcadas × classes que têm composição definida. Sem composição não há o
    # que rebalancear: a classe é pulada com aviso (e o aporte vai para as demais).
    # Classe com meta 0% não conta como "faltando composição" — ela simplesmente não faz
    # parte da carteira alvo, e cobrar uma cesta dela seria ruído.
    selected = list(req.classes or ALLOCATION_CLASSES)
    all_baskets = prefs.get("class_targets") or {}
    # A cesta de RENDA_FIXA é de tags de indexador, não de tickers com preço: ela não passa
    # pelo alocador de cotas e tem o próprio degrau na cascata do aporte.
    baskets = {
        c: b for c, b in all_baskets.items()
        if b and c in selected and c in INVESTABLE_CLASSES
    }
    skipped = [
        c for c in selected
        if c in INVESTABLE_CLASSES and c not in baskets and targets.get(c, 0.0) > 0
    ]
    if (
        RENDA_FIXA in selected
        and targets.get(RENDA_FIXA, 0.0) > 0
        and not all_baskets.get(RENDA_FIXA)
    ):
        warnings.append(
            "Renda fixa tem meta de alocação mas nenhum indexador na cesta — marque as "
            "contas que contam na carteira e dê a elas uma tag (CDI, IPCA, LCI…)."
        )
    if not baskets:
        raise HTTPException(
            status_code=422,
            detail=(
                "Nenhuma classe selecionada tem composição definida. "
                "Monte sua carteira alvo primeiro."
            ),
        )
    for c in skipped:
        warnings.append(
            f"{CLASS_LABEL.get(c, c)}: classe selecionada sem composição — pulada neste plano. "
            "Defina a carteira alvo para incluí-la."
        )
    for c in sorted(baskets):
        if targets.get(c, 0.0) <= 0:
            warnings.append(
                f"{CLASS_LABEL.get(c, c)}: a meta de alocação da classe está em 0% — "
                "sem orçamento para comprar. Ajuste a meta na Carteira alvo."
            )

    # 3) universo: só os tickers das cestas selecionadas. O fetch de mercado domina o
    # tempo do plano, então buscar apenas o que pode ser comprado é o que o torna rápido.
    try:
        assets = await build_universe(portfolio, get_cache(), get_brapi(), class_baskets=baskets)
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"Falha ao buscar dados de mercado na brapi ({exc}).")
        assets = []

    stale = [a.ticker for a in assets if a.stale]
    if stale:
        warnings.append(f"Dados defasados (cache) para: {', '.join(stale[:8])}.")

    # 4) DY-alvo de Bazin (manual ou atrelado à Selic) — define o preço-teto de cada ativo
    bazin_mode = prefs.get("bazin_target_mode") or "fixed_6"
    bazin_manual = float(prefs.get("bazin_target_yield") or 0.06)
    cdi = None
    if bazin_mode == "dynamic_selic":
        try:
            cdi = await get_sgs().cdi_annual()
        except Exception:  # noqa: BLE001
            cdi = None
    bazin_yield = resolve_bazin_target_yield(bazin_mode, bazin_manual, cdi)

    # 5) ranking = os ativos da carteira alvo, com a leitura factual de cada um
    class_of = {t.upper(): c for c, b in baskets.items() for t in b}
    ranking: list[PlanAsset] = []
    for a in assets:
        cls = class_of.get(a.ticker.upper(), a.asset_class)
        an = analyze_asset(a, bazin_yield)
        ranking.append(
            PlanAsset(
                ticker=a.ticker,
                name=a.name,
                asset_class=cls,
                sector=a.sector,
                price=a.price,
                dividend_yield=a.fundamentals.dividend_yield,
                bazin_ceiling_price=an.bazin_ceiling_price,
                bazin_below_ceiling=an.bazin_below_ceiling,
                bazin_margin=an.bazin_margin,
                risk_level=an.risk_level,
                red_flags=an.red_flags,
            )
        )

    prices = {a.ticker: (a.price or 0.0) for a in assets}
    for c, basket in sorted(baskets.items()):
        no_price = [t for t in basket if (prices.get(t) or 0.0) <= 0]
        if no_price:
            warnings.append(
                f"Sem cotação para {', '.join(sorted(no_price))} — pesos da carteira "
                f"alvo de {CLASS_LABEL.get(c, c)} renormalizados entre os demais."
            )

    # posições que você tem mas que não fazem parte da carteira alvo: não recebem compra
    # (e não somem em silêncio — é justamente o que o rebalanceamento vai diluindo)
    in_baskets = {t.upper() for b in baskets.values() for t in b}
    extras = sorted(
        p.ticker for p in portfolio.positions
        if p.asset_class in baskets and p.ticker.upper() not in in_baskets
    )
    if extras:
        warnings.append(
            f"Fora da carteira alvo: {', '.join(extras[:8])}"
            f"{f' (e mais {len(extras) - 8})' if len(extras) > 8 else ''}. "
            "Continuam na carteira, mas não recebem aporte."
        )

    # 6) piso da reserva: prioridade ABSOLUTA sobre qualquer compra. Só a renda fixa
    # LÍQUIDA (contas marcadas, de propósito 'investment' e com resgate imediato) satisfaz
    # o piso — uma LCI travada soma no peso da classe mas não serve de emergência.
    floor_nominal = (
        req.reserve_floor if req.reserve_floor is not None
        else float(prefs.get("reserve_floor_amount") or 0.0)
    )
    if req.reserve_current is not None:
        liquid_reserve = req.reserve_current
    else:
        try:
            liquid_reserve = await fixed_income_repo.liquid_reserve(get_db())
        except Exception as exc:  # noqa: BLE001
            warnings.append(
                f"Não consegui ler a renda fixa ({exc}); assumindo reserva líquida = 0."
            )
            liquid_reserve = 0.0

    floor = await resolve_floor(prefs, liquid_reserve, get_sgs(), floor_nominal)
    if floor_nominal > 0 and not floor["index_available"]:
        warnings.append(
            "Não consegui buscar o IPCA para corrigir o piso da reserva; usando o valor "
            "nominal por enquanto."
        )
    split = reserve_svc.direct_to_floor(req.aporte, floor["deficit"])
    aporte_rv = split["remaining"]

    # 7) alocação do aporte de RENDA VARIÁVEL (após o pré-corte da reserva).
    # Lote conforme a preferência: 'fracionario' compra por unidade; 'integral' respeita
    # o lote real da B3 (ações = 100; FII/ETF/BDR = 1).
    lot_mode = prefs.get("lot_mode") or "integral"
    lots = {a.ticker: (1 if lot_mode == "fracionario" else a.lot_size) for a in assets}
    unallocated = allocate(
        aporte_rv, ranking, portfolio, prices, lots, targets, baskets,
        min_ticket=req.min_ticket,
    )

    # mesma conta de necessidade do alocador — a explicação não pode divergir do motor
    total_after = portfolio.total_value + aporte_rv
    by_class = portfolio.allocations.by_class
    at_target = {
        c for c in baskets
        if targets.get(c, 0.0) * total_after - by_class.get(c, 0.0) * portfolio.total_value <= 0
    }
    for item in ranking:
        item.reasons = _plan_reasons(item, at_target)

    # 8) status do piso (só quando existe um piso configurado — sem piso, sem card)
    reserve = None
    if floor_nominal > 0:
        try:
            cdi = await get_sgs().cdi_annual()
        except Exception:  # noqa: BLE001
            cdi = None
        reserve = ReserveSuggestion(
            target_amount=floor["floor_corrected"],
            current_amount=floor["liquid_reserve"],
            gap=floor["deficit"],
            pct_filled=floor["pct_filled"],
            directed_now=split["floor_directed"],
            benchmark_cdi_annual=cdi,
            floor_nominal=floor["floor_nominal"],
            floor_date=floor["floor_date"],
            floor_index=floor["index"],
            floor_index_available=floor["index_available"],
        )

    # compras primeiro (maior valor no topo); depois o resto, ordenado pelo desconto sobre
    # o teto — é o que justifica antecipar uma compra que o rebalanceamento não pediu
    suggested = sorted(
        (r for r in ranking if r.suggested),
        key=lambda r: r.suggested.invested_exact,
        reverse=True,
    )
    others = sorted(
        (r for r in ranking if not r.suggested),
        key=lambda r: (r.bazin_margin is None, -(r.bazin_margin or 0), -(r.basket_gap_brl or 0)),
    )

    response = PlanResponse(
        aporte=req.aporte,
        as_of=datetime.now(timezone.utc).isoformat(),
        targets_by_class=targets,
        current_by_class=portfolio.allocations.by_class,
        ranking=suggested + others,
        unallocated=unallocated,
        reserve=reserve,
        classes_applied=sorted(baskets),
        classes_skipped=skipped,
        warnings=warnings,
    )

    # persiste o plano (memória de decisão + 'último plano' sobrevive à navegação)
    try:
        response.plan_id = await plans_repo.save(
            get_db(), req.model_dump(), response.model_dump()
        )
    except Exception:  # noqa: BLE001
        pass  # histórico é conveniência; não derruba o plano

    return response


@router.get("/plan/latest", response_model=PlanResponse)
async def plan_latest() -> PlanResponse:
    """Último plano gerado (persistido) — para a PlanPage restaurar ao montar."""
    data = await plans_repo.latest(get_db())
    if data is None:
        raise HTTPException(status_code=404, detail="Nenhum plano salvo ainda.")
    return PlanResponse(**data)


@router.get("/plan/history", response_model=list[PlanSummary])
async def plan_history(limit: int = 20) -> list[PlanSummary]:
    """Planos anteriores (resumo): quando, quanto e quantas compras foram sugeridas."""
    rows = await plans_repo.list_recent(get_db(), limit)
    return [PlanSummary(**r) for r in rows]
