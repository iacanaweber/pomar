"""Captura semanal do retorno da carteira — a orquestração (banco, Ghostfolio, índices).

A aritmética vive em `services/twr.py` e `services/benchmarks.py`; aqui só se decide
QUANDO capturar, o que gravar e como degradar quando uma fonte falha.

**Semana ISO fechando no domingo**, chave `yyyy-Www`, espelhando o `yyyy-mm` dos snapshots
mensais.

**O container pode estar desligado no domingo.** Por isso a captura não é um evento
agendado que se perde: no boot e periodicamente, olhamos qual foi a última semana gravada
e capturamos a semana corrente se estiver faltando. `late=1` marca a captura que saiu fora
da janela pretendida (não no próprio domingo ou na segunda), para o gráfico não mentir
sobre a data do dado.

**Semana perdida é LACUNA, não valor inventado.** Não reconstruímos semanas passadas com
preço de hoje: o preço de hoje não é o preço daquele domingo, e preencher a série assim
produziria um gráfico que parece completo e está errado.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.repositories import fixed_income_repo, labels_repo, weekly_repo
from app.repositories.db import Database
from app.services import benchmarks as bm
from app.services import fixed_income as fi
from app.services import twr
from app.util import from_cents, to_cents

log = logging.getLogger("pomar.weekly")

# Até quantos dias depois do domingo a captura ainda é considerada "na janela". Dois dias
# cobre o container que só sobe na segunda de manhã.
ON_TIME_DAYS = 2


def _hoje() -> date:
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo("America/Sao_Paulo")).date()


async def _portfolio_value(ghostfolio, cache, db: Database) -> Dict[str, Any]:
    """Patrimônio de hoje: renda variável + renda fixa marcada. Uma falha do Ghostfolio
    não zera a renda fixa — e é dito no retorno, não engolido."""
    from app.services.portfolio_service import get_enriched_portfolio

    rv, avisos, posicoes = 0.0, [], []
    try:
        overrides = await labels_repo.bucket_overrides(db)
        pf = await get_enriched_portfolio(ghostfolio, cache, overrides)
        rv = pf.total_value
        posicoes = [{"ticker": p.ticker, "value": p.value, "class": p.asset_class}
                    for p in pf.positions]
    except Exception as exc:  # noqa: BLE001
        avisos.append(f"Ghostfolio indisponível ({exc}).")

    contas = [a for a in await fixed_income_repo.balances(db) if fi.counts_in_portfolio(a)]
    rf = from_cents(sum(to_cents(a["balance"]) for a in contas))
    return {
        "rv": round(rv, 2),
        "rf": rf,
        "total": from_cents(to_cents(rv) + to_cents(rf)),
        "posicoes": posicoes,
        "avisos": avisos,
    }


async def _all_flows(ghostfolio, db: Database) -> tuple[List[Dict[str, Any]], List[str]]:
    """Fluxos das DUAS fontes: Ghostfolio (renda variável) e o rastreador (renda fixa).

    A renda fixa nunca esteve no Ghostfolio — as caixinhas e o Tesouro só existem aqui —
    então usar uma fonte só deixaria metade do dinheiro sem neutralizar.
    """
    avisos: List[str] = []
    fluxos: List[Dict[str, Any]] = []
    try:
        fluxos += twr.normalize_flows(await ghostfolio.get_activities())
    except Exception as exc:  # noqa: BLE001
        avisos.append(
            f"Transações do Ghostfolio ilegíveis ({exc}). Os aportes do período não foram "
            "neutralizados e o retorno sai superestimado."
        )
    try:
        contas = await fixed_income_repo.list_accounts(db, include_archived=True)
        for acc in contas:
            if not fi.counts_in_portfolio(acc):
                continue
            entries = await fixed_income_repo.list_entries(db, acc["id"])
            fluxos += twr.fixed_income_flows(entries)
    except Exception as exc:  # noqa: BLE001
        avisos.append(f"Lançamentos da renda fixa ilegíveis ({exc}).")
    return fluxos, avisos


async def collect_benchmarks(db: Database, brapi, sgs, when: date) -> Dict[str, Any]:
    """Grava o nível de cada índice na data. Cada série falha sozinha.

    Nunca levanta: falha de índice não pode impedir o snapshot da carteira, que é o dado
    insubstituível — o índice dá para buscar de novo depois, a carteira daquele domingo não.
    """
    ok, falhas = [], []
    pregao = bm.business_day_before(when)

    # 1) índices e proxies via brapi (o nível é a própria cotação)
    for code, ticker in bm._BRAPI_TICKERS.items():
        try:
            assets = await brapi.get_assets([ticker])
            preco = next((a.price for a in assets if a.price), None)
            if preco:
                await weekly_repo.save_level(db, code, pregao.isoformat(), preco,
                                             bm.BENCHMARKS[code]["source"])
                ok.append(code)
            else:
                falhas.append(code)
        except Exception as exc:  # noqa: BLE001
            log.warning("benchmark %s falhou: %r", code, exc)
            falhas.append(code)

    # 2) séries do Banco Central. CDI e IPCA são TAXAS: acumulamos desde o início da série
    #    guardada para manter um nível base 100 coerente entre capturas.
    for code, serie in (("CDI", bm.SGS_CDI), ("IPCA", bm.SGS_IPCA)):
        try:
            inicio = date(when.year - 3, 1, 1)
            obs = await sgs.series_range(serie, inicio, when)
            if not obs:
                falhas.append(code)
                continue
            for ponto in bm.accumulate(obs):
                await weekly_repo.save_level(db, code, ponto["date"], ponto["level"],
                                             bm.BENCHMARKS[code]["source"])
            ok.append(code)
        except Exception as exc:  # noqa: BLE001
            log.warning("benchmark %s falhou: %r", code, exc)
            falhas.append(code)

    # 3) dólar já vem como nível
    try:
        obs = await sgs.series_range(bm.SGS_USD, when - timedelta(days=30), when)
        if obs:
            ultimo = obs[-1]
            await weekly_repo.save_level(db, "USDBRL", ultimo["date"].isoformat(),
                                         ultimo["value"], bm.BENCHMARKS["USDBRL"]["source"])
            ok.append("USDBRL")
        else:
            falhas.append("USDBRL")
    except Exception as exc:  # noqa: BLE001
        log.warning("benchmark USDBRL falhou: %r", exc)
        falhas.append("USDBRL")

    return {"ok": sorted(ok), "falhas": sorted(falhas)}


async def capture_week(
    db: Database, ghostfolio, cache, brapi=None, sgs=None,
    when: Optional[date] = None, force: bool = False,
) -> Dict[str, Any]:
    """Captura a semana de `when` (padrão: hoje). Idempotente — não sobrescreve.

    O retorno do período é medido contra a ÚLTIMA semana gravada, não contra a semana
    imediatamente anterior no calendário: se houve lacuna, o período é mais longo e os
    fluxos da lacuna inteira entram na conta. É a leitura honesta de uma série com buraco.
    """
    hoje = when or _hoje()
    fechamento = twr.week_end(hoje)
    # Semana ainda em curso: fecha no domingo. Capturar antes gravaria um "fechamento"
    # que não fechou, e ele nunca mais seria corrigido (a série é congelada).
    if fechamento > hoje and not force:
        fechamento -= timedelta(days=7)
    chave = twr.week_key(fechamento)

    if await weekly_repo.get_week(db, chave):
        return {"saved": False, "week_of": chave, "reason": "já capturada"}

    valores = await _portfolio_value(ghostfolio, cache, db)
    avisos = list(valores["avisos"])
    if valores["total"] <= 0:
        return {"saved": False, "week_of": chave, "reason": "patrimônio zerado",
                "warnings": avisos}

    anterior = await weekly_repo.last_week(db)
    fluxos, avisos_fluxo = await _all_flows(ghostfolio, db)
    avisos += avisos_fluxo

    if anterior:
        inicio = date.fromisoformat(anterior["week_end"])
        valor_inicial = float(anterior["total_value"])
        acumulado_anterior = anterior["twr_cumulative"]
    else:
        # Primeira captura: não há período anterior, então não há retorno a medir. O
        # ponto entra com TWR zero — é a origem da série, não um retorno de zero.
        inicio = fechamento
        valor_inicial = valores["total"]
        acumulado_anterior = 0.0

    do_periodo = twr.flows_between(fluxos, inicio, fechamento)
    periodo = twr.period_return(valor_inicial, valores["total"], do_periodo, inicio, fechamento)
    acumulado = (
        twr.chain([acumulado_anterior, periodo["r"]])
        if anterior else 0.0
    )

    if brapi is not None and sgs is not None:
        indices = await collect_benchmarks(db, brapi, sgs, fechamento)
        if indices["falhas"]:
            avisos.append(f"Índices sem dado nesta captura: {', '.join(indices['falhas'])}.")

    atraso = (hoje - fechamento).days
    gravou = await weekly_repo.save_week(
        db,
        week_of=chave,
        week_end=fechamento.isoformat(),
        late=atraso > ON_TIME_DAYS,
        total_value=valores["total"],
        rv_value=valores["rv"],
        rf_value=valores["rf"],
        flow_net=periodo["net"],
        flow_weighted=periodo["weighted"],
        twr_period=periodo["r"],
        twr_cumulative=acumulado,
        flows=do_periodo,
        detail={"posicoes": valores["posicoes"], "capturado_em_dias": atraso},
    )
    return {
        "saved": gravou, "week_of": chave, "week_end": fechamento.isoformat(),
        "late": atraso > ON_TIME_DAYS, "total_value": valores["total"],
        "twr_period": periodo["r"], "twr_cumulative": acumulado, "warnings": avisos,
    }


async def catch_up(db: Database, ghostfolio, cache, brapi=None, sgs=None) -> Dict[str, Any]:
    """Captura a semana corrente se estiver faltando. Chamado no boot e periodicamente.

    NÃO preenche semanas passadas: sem o preço daquele domingo, o valor seria inventado.
    As semanas ausentes ficam como lacuna e a interface as mostra como tal.
    """
    resultado = await capture_week(db, ghostfolio, cache, brapi, sgs)
    if resultado.get("saved"):
        log.info("snapshot semanal gravado: %s", resultado["week_of"])
    return resultado


def gaps(weeks: List[Dict[str, Any]]) -> List[str]:
    """Semanas ausentes entre a primeira e a última gravadas — para a tela ser honesta
    sobre onde a série tem buraco em vez de ligar os pontos como se não houvesse."""
    if len(weeks) < 2:
        return []
    datas = [date.fromisoformat(w["week_end"]) for w in weeks]
    esperadas = twr.weeks_between(datas[0], datas[-1])
    existentes = {d.isoformat() for d in datas}
    return [twr.week_key(d) for d in esperadas if d.isoformat() not in existentes]
