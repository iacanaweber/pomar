"""Curva de rendimento: TWR semanal da carteira contra os índices de comparação."""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Dict, List

from fastapi import APIRouter, HTTPException, Query

from app.config import get_settings
from app.deps import get_brapi, get_cache, get_db, get_ghostfolio, get_sgs
from app.models.performance import BenchmarkSeries, PerformanceResponse, WeeklyPoint
from app.repositories import labels_repo, preferences_repo, weekly_repo
from app.services import benchmarks as bm
from app.services import indexers as indexers_svc
from app.services import twr, weekly

router = APIRouter()

WINDOW_DAYS = {"3m": 92, "6m": 183, "12m": 366}


@router.get("/performance", response_model=PerformanceResponse)
async def performance(
    window: str = Query("all", pattern="^(3m|6m|12m|all)$"),
) -> PerformanceResponse:
    db = get_db()
    settings = get_settings()
    warnings: List[str] = []

    todas = await weekly_repo.list_weeks(db)
    if not todas:
        return PerformanceResponse(
            window=window,
            warnings=[
                "Série semanal vazia. O primeiro ponto é gravado no fechamento de domingo."
            ],
        )

    # Recorte da janela. O ponto imediatamente ANTERIOR ao corte entra como base: sem ele,
    # o primeiro retorno da janela seria medido contra o nada.
    if window != "all":
        limite = date.today() - timedelta(days=WINDOW_DAYS[window])
        dentro = [w for w in todas if date.fromisoformat(w["week_end"]) >= limite]
        if len(dentro) < len(todas):
            idx = todas.index(dentro[0]) if dentro else len(todas) - 1
            dentro = todas[max(0, idx - 1):]
        pontos = dentro or todas[-1:]
    else:
        pontos = todas

    # O TWR guardado é acumulado desde o INÍCIO da série. Para a janela, reencadeamos os
    # retornos de período — é por isso que `twr_period` é gravado junto do acumulado.
    rebase = twr.chain([w["twr_period"] for w in pontos[1:]])
    datas = [date.fromisoformat(w["week_end"]) for w in pontos]

    saida_pontos: List[WeeklyPoint] = []
    acumulado = 0.0
    for i, w in enumerate(pontos):
        if i == 0:
            acc = 0.0
        else:
            acumulado = twr.chain([acumulado, w["twr_period"]]) or acumulado
            acc = acumulado
        saida_pontos.append(WeeklyPoint(
            week_of=w["week_of"], week_end=w["week_end"], captured_at=w["captured_at"],
            late=bool(w["late"]), total_value=w["total_value"],
            rv_value=w["rv_value"], rf_value=w["rf_value"],
            flow_net=w["flow_net"], twr_period=w["twr_period"], twr_cumulative=acc,
        ))

    # Índices, todos rebaseados no primeiro ponto da janela — é o que faz as curvas
    # partirem do mesmo zero e a comparação com o TWR ser legível.
    por_codigo = await weekly_repo.all_levels(db)
    series: List[BenchmarkSeries] = []
    for code, meta in bm.BENCHMARKS.items():
        valores = bm.cumulative_series(por_codigo.get(code, []), datas)
        if all(v is None for v in valores):
            continue
        series.append(BenchmarkSeries(
            code=code, label=meta["label"], source=meta["source"],
            proxy=meta["proxy"], values=valores,
        ))

    # Benchmark composto: os pesos da carteira ALVO do próprio usuário. É o único
    # comparável metodologicamente defensável — confronta a execução da estratégia com a
    # estratégia. O Ibovespa fica na tela como referência cultural, não como critério.
    prefs = await preferences_repo.get(db, settings)
    geo = {}
    try:
        exposicao = await labels_repo.assignments_by_subject(db, "geography", "ticker")
        intl = sum(
            lab["weight"] for labs in exposicao.values() for lab in labs if lab["code"] == "INTL"
        )
        total_rot = sum(lab["weight"] for labs in exposicao.values() for lab in labs) or 1.0
        geo = {"INTL": intl / total_rot}
    except Exception:  # noqa: BLE001
        pass
    pesos = bm.compose_weights(
        prefs.get("targets") or {},
        etf_geography=geo,
        rf_indexers=(prefs.get("class_targets") or {}).get("RENDA_FIXA") or {},
    )
    if pesos:
        composto = bm.composite_series(pesos, por_codigo, datas)
        if any(v is not None for v in composto):
            series.append(BenchmarkSeries(
                code="COMPOSITE", label="Sua estratégia", proxy=None,
                source="pesos da sua carteira alvo",
                values=composto,
            ))

    # XIRR sobre os fluxos congelados da janela + o valor final. Responde "quanto o meu
    # dinheiro rendeu" e por isso NÃO é comparado com índice.
    fluxos: List[Dict] = []
    for w in pontos[1:]:
        try:
            fluxos += json.loads(w["flows_json"] or "[]")
        except (TypeError, ValueError):
            continue
    valor_final = pontos[-1]["total_value"]
    xirr = twr.money_weighted_return(
        fluxos, valor_final, datas[-1],
        initial_value=pontos[0]["total_value"], initial_date=datas[0],
    ) if len(pontos) > 1 else None

    dias = (datas[-1] - datas[0]).days
    if any(p.late for p in saida_pontos):
        warnings.append(
            "Alguns pontos foram capturados fora da janela do domingo."
        )
    buracos = weekly.gaps(pontos)
    if buracos:
        warnings.append(
            f"{len(buracos)} semana(s) sem captura. A série mostra a lacuna."
        )
    if len(saida_pontos) < 4:
        warnings.append(
            "Menos de quatro pontos: use a tabela."
        )

    return PerformanceResponse(
        points=saida_pontos, benchmarks=series, composite_weights=pesos,
        twr=rebase, twr_annualized=twr.annualize(rebase, dias), xirr=xirr,
        invested=round(sum(float(f.get("amount", 0)) for f in fluxos), 2),
        current_value=valor_final, window=window, gaps=buracos, warnings=warnings,
    )


@router.post("/performance/capture")
async def capture(force: bool = False) -> dict:
    """Captura a semana agora — o mesmo caminho do agendador, exposto para uso manual."""
    try:
        return await weekly.capture_week(
            get_db(), get_ghostfolio(), get_cache(), get_brapi(), get_sgs(), force=force
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Falha ao capturar a semana: {exc}")
