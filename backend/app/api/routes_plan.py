"""Rota central: gera o plano de aporte do dia."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from app.config import STRATEGY_PRESETS, get_settings
from app.deps import get_brapi, get_cache, get_ghostfolio, get_db, get_sgs
from app.models.portfolio import Allocations, Portfolio
from app.models.scoring import PlanRequest, PlanResponse, ReserveSuggestion
from app.repositories import fixed_income_repo, preferences_repo
from app.services import reserve as reserve_svc
from app.services.allocation import allocate
from app.services.portfolio_service import get_enriched_portfolio
from app.services.scoring import resolve_bazin_target_yield, score_assets
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

    # 3) preferências do usuário: DY-alvo de Bazin (manual ou atrelado à Selic) + reserva
    prefs = await preferences_repo.get(get_db(), settings)
    bazin_mode = prefs.get("bazin_target_mode") or "fixed_6"
    bazin_manual = float(prefs.get("bazin_target_yield") or 0.06)
    cdi = None
    if bazin_mode == "dynamic_selic":
        try:
            cdi = await get_sgs().cdi_annual()
        except Exception:  # noqa: BLE001
            cdi = None
    bazin_yield = resolve_bazin_target_yield(bazin_mode, bazin_manual, cdi)

    # score (a estratégia também aplica filtros de elegibilidade, não só pesos)
    ranking = score_assets(
        assets, portfolio, targets, weights, strategy=req.strategy, bazin_target_yield=bazin_yield
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
    lots = {a.ticker: a.lot_size for a in assets}
    unallocated = allocate(
        aporte_rv, ranking, portfolio, prices, lots, targets,
        max_assets=req.max_assets,
        max_weight_per_asset=req.max_weight_per_asset,
        min_ticket=req.min_ticket,
        max_weight_per_class=req.max_weight_per_class,
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

    return PlanResponse(
        aporte=req.aporte,
        as_of=datetime.now(timezone.utc).isoformat(),
        weights=weights,
        targets_by_class=targets,
        current_by_class=portfolio.allocations.by_class,
        ranking=suggested + others,
        unallocated=unallocated,
        reserve=reserve,
        warnings=warnings,
    )
