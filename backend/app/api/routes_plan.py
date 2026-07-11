"""Rota central: gera o plano de aporte do dia."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.config import STRATEGY_PRESETS, get_settings
from app.deps import get_brapi, get_cache, get_ghostfolio, get_db, get_sgs
from app.models.portfolio import Allocations, Portfolio
from app.models.scoring import PlanRequest, PlanResponse, PlanSummary, ReserveSuggestion
from app.repositories import fixed_income_repo, plans_repo, preferences_repo, watchlist_repo
from app.services import reserve as reserve_svc
from app.services.allocation import allocate
from app.services.portfolio_service import get_enriched_portfolio
from app.services.scoring import resolve_bazin_target_yield, score_assets
from app.services.strategies import STRATEGY_FILTERS
from app.services.universe import build_universe

router = APIRouter()


def _resolve_weights(req: PlanRequest) -> dict:
    if req.weights:
        return req.weights
    preset = STRATEGY_PRESETS.get(req.strategy, STRATEGY_PRESETS["equilibrado"])
    return dict(preset["weights"])


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
    weights = _resolve_weights(req)

    # 1.5) foco + restrições de candidatos (cesta > favoritos > watchlist inteira).
    # As preferências entram aqui porque o foco/cesta decidem O QUE buscar no mercado.
    prefs = await preferences_repo.get(get_db(), settings)
    focus = req.focus or (prefs.get("focus") or "BALANCE")
    baskets = {c: b for c, b in (prefs.get("class_targets") or {}).items() if b}
    try:
        favorites = await watchlist_repo.favorites(get_db())
    except Exception:  # noqa: BLE001
        favorites = {}
    if focus != "BALANCE":
        baskets = {c: b for c, b in baskets.items() if c == focus}
        favorites = {c: t for c, t in favorites.items() if c == focus}
    # favoritos só valem onde não há cesta (a cesta é mais específica)
    favorites = {c: t for c, t in favorites.items() if t and c not in baskets}
    for c, ticks in sorted(favorites.items()):
        warnings.append(f"⭐ {c}: considerando só seus {len(ticks)} favoritos.")
    for c, basket in sorted(baskets.items()):
        warnings.append(f"🎯 {c}: carteira alvo aplicada ({len(basket)} ativos).")
    user_picked = {t for ticks in favorites.values() for t in ticks}
    for basket in baskets.values():
        user_picked.update(basket)

    # 2) universo + dados de mercado (já restrito ao foco/favoritos/cesta — o fetch de
    # mercado domina o tempo do plano, então filtrar antes é o que torna o foco barato)
    try:
        assets = await build_universe(
            portfolio, get_cache(), get_brapi(),
            focus=focus, favorites=favorites, class_baskets=baskets,
        )
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"Falha ao buscar dados de mercado na brapi ({exc}).")
        assets = []

    stale = [a.ticker for a in assets if a.stale]
    if stale:
        warnings.append(f"Dados defasados (cache) para: {', '.join(stale[:8])}.")
    no_data = [a.ticker for a in assets if "all" in a.missing]
    if no_data:
        extra = f" (e mais {len(no_data) - 8})" if len(no_data) > 8 else ""
        warnings.append(f"Sem cotação para: {', '.join(no_data[:8])}{extra}.")

    # 3) preferências do usuário: DY-alvo de Bazin (manual ou atrelado à Selic) + reserva
    bazin_mode = prefs.get("bazin_target_mode") or "fixed_6"
    bazin_manual = float(prefs.get("bazin_target_yield") or 0.06)
    cdi = None
    if bazin_mode == "dynamic_selic":
        try:
            cdi = await get_sgs().cdi_annual()
        except Exception:  # noqa: BLE001
            cdi = None
    bazin_yield = resolve_bazin_target_yield(bazin_mode, bazin_manual, cdi)

    # score (a estratégia também aplica filtros de elegibilidade, não só pesos; favoritos
    # e tickers de cesta não são zerados pelo filtro — a escolha explícita do usuário manda)
    ranking = score_assets(
        assets, portfolio, targets, weights, strategy=req.strategy,
        bazin_target_yield=bazin_yield, user_picked=user_picked,
    )

    # Transparência: se a estratégia zerou uma classe inteira com alvo > 0 (ex.: Barsi
    # exclui FIIs), avisa — antes o orçamento era realocado em silêncio e a carteira
    # derivava dos alvos que o próprio usuário definiu.
    if req.strategy in STRATEGY_FILTERS:
        for cls, tgt in targets.items():
            if tgt <= 0:
                continue
            cls_ranked = [r for r in ranking if r.asset_class == cls]
            if cls_ranked and all(r.composite_score <= 0 for r in cls_ranked):
                warnings.append(
                    f"A estratégia '{req.strategy}' excluiu todos os candidatos de {cls} "
                    f"(alvo de {tgt * 100:.0f}%) — esse valor foi realocado para as demais classes."
                )

    # 3.5) reserva / renda fixa: prioriza completar a reserva antes da RV (Barsi/Bazin).
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

    # 4) alocação do aporte de RENDA VARIÁVEL (após o pré-corte da reserva)
    prices = {a.ticker: (a.price or 0.0) for a in assets}
    for c, basket in sorted(baskets.items()):
        no_price = [t for t in basket if (prices.get(t) or 0.0) <= 0]
        if no_price:
            warnings.append(
                f"Sem cotação para {', '.join(sorted(no_price))} — pesos da carteira "
                f"alvo de {c} renormalizados entre os demais."
            )
    # lote conforme a preferência: 'fracionario' compra por unidade; 'integral' respeita
    # o lote real da B3 (ações = 100; FII/ETF/BDR = 1)
    lot_mode = prefs.get("lot_mode") or "integral"
    lots = {a.ticker: (1 if lot_mode == "fracionario" else a.lot_size) for a in assets}

    # posições que o filtro de favoritos/cesta exclui podem aparecer no ranking (já são
    # suas), mas não recebem compra; com foco, todo o aporte de RV mira a classe focada
    def _allowed_buy(r) -> bool:
        if r.asset_class in baskets:
            return r.ticker in baskets[r.asset_class]
        if r.asset_class in favorites:
            return r.ticker in favorites[r.asset_class]
        return True

    alloc_ranking = [r for r in ranking if _allowed_buy(r)]
    targets_alloc = {focus: 1.0} if focus != "BALANCE" else targets
    unallocated = allocate(
        aporte_rv, alloc_ranking, portfolio, prices, lots, targets_alloc,
        max_assets=req.max_assets,
        max_weight_per_asset=req.max_weight_per_asset,
        min_ticket=req.min_ticket,
        max_weight_per_class=None if focus != "BALANCE" else req.max_weight_per_class,
        class_baskets=baskets,
    )

    # 4.5) sugestão de reserva (só quando há alvo de reserva definido)
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

    # mostra apenas os ativos com sugestão de compra primeiro, depois o resto do ranking
    suggested = [r for r in ranking if r.suggested]
    others = [r for r in ranking if not r.suggested][: max(0, 15 - len(suggested))]

    response = PlanResponse(
        aporte=req.aporte,
        as_of=datetime.now(timezone.utc).isoformat(),
        weights=weights,
        targets_by_class=targets,
        current_by_class=portfolio.allocations.by_class,
        ranking=suggested + others,
        unallocated=unallocated,
        reserve=reserve,
        warnings=warnings,
        focus=focus,
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
    """Planos anteriores (resumo): quando, quanto, qual estratégia, nº de sugestões."""
    rows = await plans_repo.list_recent(get_db(), limit)
    return [PlanSummary(**r) for r in rows]
