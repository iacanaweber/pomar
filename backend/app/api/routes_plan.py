"""Rota central: gera o plano de aporte do dia."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from app.config import STRATEGY_PRESETS, get_settings
from app.deps import get_brapi, get_cache, get_ghostfolio
from app.models.portfolio import Allocations, Portfolio
from app.models.scoring import PlanRequest, PlanResponse
from app.services.allocation import allocate
from app.services.portfolio_service import get_enriched_portfolio
from app.services.scoring import score_assets
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

    # 1) carteira atual (degrada para carteira vazia se o Ghostfolio falhar)
    try:
        portfolio = await get_enriched_portfolio(get_ghostfolio(), get_cache())
    except Exception as exc:  # noqa: BLE001
        warnings.append(
            f"Não consegui ler o Ghostfolio ({exc}); seguindo com carteira vazia. "
            "O rebalanceamento vai mirar diretamente os alvos."
        )
        portfolio = Portfolio(
            total_value=0.0, as_of=datetime.now(timezone.utc).isoformat(),
            allocations=Allocations(),
        )

    targets = req.targets or settings.default_targets
    weights = _resolve_weights(req)

    # 2) universo + dados de mercado
    try:
        assets = await build_universe(portfolio, get_cache(), get_brapi())
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

    # 3) score (a estratégia também aplica filtros de elegibilidade, não só pesos)
    ranking = score_assets(assets, portfolio, targets, weights, strategy=req.strategy)

    # 4) alocação do aporte
    prices = {a.ticker: (a.price or 0.0) for a in assets}
    lots = {a.ticker: a.lot_size for a in assets}
    unallocated = allocate(
        req.aporte, ranking, portfolio, prices, lots, targets,
        max_assets=req.max_assets,
        max_weight_per_asset=req.max_weight_per_asset,
        min_ticket=req.min_ticket,
    )

    # mostra apenas os ativos com sugestão de compra primeiro, depois o resto do ranking
    suggested = [r for r in ranking if r.suggested]
    others = [r for r in ranking if not r.suggested][: max(0, 15 - len(suggested))]

    return PlanResponse(
        aporte=req.aporte,
        as_of=datetime.now(timezone.utc).isoformat(),
        weights=weights,
        targets_by_class=targets,
        current_by_class=portfolio.allocations.by_class,
        ranking=suggested + others,
        unallocated=unallocated,
        warnings=warnings,
    )
