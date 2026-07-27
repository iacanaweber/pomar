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
    INVESTABLE_CLASSES,
    PlanAsset,
    PlanRequest,
    PlanResponse,
    PlanSummary,
    ReserveSuggestion,
)
from app.models.portfolio import Allocations, Portfolio
from app.repositories import fixed_income_repo, plans_repo, preferences_repo
from app.services import reserve as reserve_svc
from app.services.allocation import allocate
from app.services.analysis import analyze_asset, resolve_bazin_target_yield
from app.services.portfolio_service import get_enriched_portfolio
from app.services.universe import build_universe

router = APIRouter()

CLASS_LABEL = {"STOCK": "Ações", "FII": "FIIs", "ETF": "ETFs", "BDR": "BDRs"}

# Diferença mínima (em pontos percentuais) para dizer que o ativo está "abaixo do alvo".
GAP_PP_MIN = 0.5


def _plan_reasons(item: PlanAsset) -> list[str]:
    """Frases factuais: por que este ativo recebeu (ou não) compra neste plano."""
    out: list[str] = []
    label = CLASS_LABEL.get(item.asset_class, item.asset_class)
    if item.basket_target_pct is not None and item.basket_current_pct is not None:
        gap_pp = (item.basket_target_pct - item.basket_current_pct) * 100
        if gap_pp >= GAP_PP_MIN:
            out.append(f"Está {gap_pp:.1f} p.p. abaixo do alvo na cesta de {label}")
    if item.bazin_below_ceiling and item.bazin_margin:
        out.append(f"Desconto de {item.bazin_margin * 100:.0f}% sobre o preço-teto de Bazin")
    if item.suggested is None:
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
        portfolio = await get_enriched_portfolio(get_ghostfolio(), get_cache())
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

    targets = req.targets or settings.default_targets
    prefs = await preferences_repo.get(get_db(), settings)

    # 2) classes marcadas × classes que têm composição definida. Sem composição não há o
    # que rebalancear: a classe é pulada com aviso (e o aporte vai para as demais).
    selected = list(req.classes or INVESTABLE_CLASSES)
    all_baskets = prefs.get("class_targets") or {}
    baskets = {c: b for c, b in all_baskets.items() if b and c in selected}
    skipped = [c for c in selected if c not in baskets]
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

    # 6) reserva / renda fixa: prioriza completar a reserva antes da RV (Barsi/Bazin)
    reserve_target = (
        req.reserve_target if req.reserve_target is not None
        else float(prefs.get("reserve_target") or 0.0)
    )
    if req.reserve_current is not None:
        reserve_current = req.reserve_current
    else:
        try:
            reserve_current = await fixed_income_repo.total_balance(get_db())
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Não consegui ler a renda fixa ({exc}); assumindo reserva atual = 0.")
            reserve_current = 0.0
    split = reserve_svc.split_aporte_reserva(
        req.aporte, portfolio.total_value, reserve_current, reserve_target
    )
    aporte_rv = split["aporte_rv"]

    # 7) alocação do aporte de RENDA VARIÁVEL (após o pré-corte da reserva).
    # Lote conforme a preferência: 'fracionario' compra por unidade; 'integral' respeita
    # o lote real da B3 (ações = 100; FII/ETF/BDR = 1).
    lot_mode = prefs.get("lot_mode") or "integral"
    lots = {a.ticker: (1 if lot_mode == "fracionario" else a.lot_size) for a in assets}
    unallocated = allocate(
        aporte_rv, ranking, portfolio, prices, lots, targets, baskets,
        min_ticket=req.min_ticket,
    )

    for item in ranking:
        item.reasons = _plan_reasons(item)

    # 8) sugestão de reserva (só quando há alvo de reserva definido)
    reserve = None
    if reserve_target > 0:
        status = reserve_svc.reserve_status(
            portfolio.total_value, reserve_current, reserve_target, req.aporte
        )
        try:
            cdi = await get_sgs().cdi_annual()
        except Exception:  # noqa: BLE001
            cdi = None
        reserve = ReserveSuggestion(
            target_amount=status["target_amount"],
            current_amount=status["current_amount"],
            gap=status["gap"],
            pct_filled=status["pct_filled"],
            directed_now=split["reserve_directed"],
            benchmark_cdi_annual=cdi,
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
