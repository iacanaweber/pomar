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
    FixedIncomeSuggestion,
    IndexerAllocation,
    LegacySummary,
    PlanAsset,
    PlanRequest,
    PlanResponse,
    PlanSummary,
    ReserveSuggestion,
)
from app.models.portfolio import Allocations, Portfolio
from app.repositories import fixed_income_repo, labels_repo, plans_repo, preferences_repo
from app.util import from_cents, to_cents
from app.data.labels_seed import NO_INDEXER_CODE, NO_INDEXER_NAME
from app.services import cascade
from app.services import exposure as exposure_svc
from app.services import fixed_income as fi
from app.services import indexers as indexers_svc
from app.services import legacy as legacy_svc
from app.services import reserve as reserve_svc
from app.services.allocation import aligned_value_by_class, allocate, class_needs
from app.services.analysis import analyze_asset, resolve_bazin_target_yield
from app.services.portfolio_service import get_enriched_portfolio
from app.services.reserve_service import resolve_floor
from app.services.universe import build_universe

router = APIRouter()


# Diferença mínima (em pontos percentuais) para dizer que o ativo está "abaixo do alvo".
GAP_PP_MIN = 0.5


def _brl(value: float) -> str:
    """Formata em reais no padrão brasileiro (1.234,56) para as frases do plano."""
    return f"R$ {value:,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".")


def _fracoes(valores: dict[str, float], total: float) -> dict[str, float]:
    """{classe: fração do patrimônio}. Sem patrimônio, dicionário vazio — nunca Infinity."""
    if total <= 0:
        return {}
    return {c: round(v / total, 6) for c, v in valores.items()}


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
            out.append(f"{gap_pp:.1f} p.p. abaixo do alvo em {label}")
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
            out.append("No peso-alvo ou acima.")
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
                    f"Ghostfolio ilegível ({exc}) e sem cache. Plano cancelado. Use "
                    "'planejar sem a carteira' para mirar só os alvos."
                ),
            )
        warnings.append(
            f"Ghostfolio ilegível ({exc}). Planejando sem carteira: mira os alvos direto."
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
    # A classe RENDA_FIXA continua fora de INVESTABLE_CLASSES: ela tem o próprio degrau na
    # cascata e a compra dela não disputa orçamento com a bolsa. Mas a cesta dela pode ter
    # TICKERS (um ETF de renda fixa), e esses precisam de cotação e lote como qualquer
    # outro — daí as duas listas.
    baskets = {
        c: b for c, b in all_baskets.items()
        if b and c in selected and c in INVESTABLE_CLASSES
    }
    rf_tags, rf_tickers = indexers_svc.split_basket(all_baskets.get(RENDA_FIXA))
    if RENDA_FIXA not in selected:
        rf_tickers = {}
    # O universo é o que precisa de COTAÇÃO — inclui os tickers da renda fixa. As tags
    # ficam de fora: pedir preço de "CDI" não é uma pergunta com resposta.
    universe_baskets = dict(baskets)
    if rf_tickers:
        universe_baskets[RENDA_FIXA] = rf_tickers
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
            "Renda fixa com meta e sem indexador na cesta. Marque as contas que contam "
            "na carteira e dê a elas uma tag (CDI, IPCA, LCI)."
        )
    if not baskets and not rf_tickers:
        raise HTTPException(
            status_code=422,
            detail=(
                "Nenhuma classe selecionada tem composição. Defina a carteira alvo."
            ),
        )
    for c in skipped:
        warnings.append(
            f"{CLASS_LABEL.get(c, c)}: sem composição. Fora deste plano."
        )
    for c in sorted(baskets):
        if targets.get(c, 0.0) <= 0:
            warnings.append(
                f"{CLASS_LABEL.get(c, c)}: meta em 0%. Sem orçamento para comprar."
            )

    # 3) universo: só os tickers das cestas selecionadas. O fetch de mercado domina o
    # tempo do plano, então buscar apenas o que pode ser comprado é o que o torna rápido.
    try:
        assets = await build_universe(
            portfolio, get_cache(), get_brapi(), class_baskets=universe_baskets
        )
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"brapi indisponível ({exc}).")
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
    class_of = {t.upper(): c for c, b in universe_baskets.items() for t in b}
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
    for c, basket in sorted(universe_baskets.items()):
        no_price = [t for t in basket if (prices.get(t) or 0.0) <= 0]
        if no_price:
            warnings.append(
                f"Sem cotação para {', '.join(sorted(no_price))}. Pesos de "
                f"{CLASS_LABEL.get(c, c)} renormalizados."
            )

    # posições fora da carteira alvo: não recebem compra e não somem em silêncio — é
    # justamente o que o rebalanceamento vai diluindo. O resumo em R$ é montado depois da
    # alocação, quando o gap já é conhecido.
    legacy_items = legacy_svc.legacy_positions(
        [p.model_dump() for p in portfolio.positions], all_baskets, targets
    )
    if legacy_items:
        nomes = [p["ticker"] for p in legacy_items]
        warnings.append(
            f"Fora do alvo: {', '.join(nomes[:8])}"
            f"{f' (+{len(nomes) - 8})' if len(nomes) > 8 else ''}. Não recebem aporte."
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
                f"Renda fixa ilegível ({exc}). Reserva líquida = 0."
            )
            liquid_reserve = 0.0

    floor = await resolve_floor(prefs, liquid_reserve, get_sgs(), floor_nominal)
    if floor_nominal > 0 and not floor["index_available"]:
        warnings.append(
            "IPCA indisponível. Piso da reserva no valor nominal."
        )
    # 6b) CASCATA: piso → peso da classe RENDA_FIXA → renda variável.
    # A base dos alvos em R$ passa a incluir a renda fixa que conta na carteira: enquanto
    # ela ficava de fora, uma carteira 30% em Tesouro Selic mirava alvos calculados como
    # se aquele dinheiro não existisse, e as classes de renda variável pediam aporte a mais.
    try:
        contas_rf = [
            a for a in await fixed_income_repo.balances(get_db()) if fi.counts_in_portfolio(a)
        ]
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"Contas de renda fixa ilegíveis ({exc}).")
        contas_rf = []
    # A composição sai da MESMA função pura da aba Carteira: ela soma cada posição e cada
    # conta uma vez só, então o valor da classe já vem sem a dupla contagem que a soma
    # manual daqui produzia. Zero I/O e zero query — os dois insumos já estão em mãos.
    posicoes = [
        {"ticker": p.ticker, "asset_class": p.asset_class, "sector": p.sector, "value": p.value}
        for p in portfolio.positions
    ]
    composicao = exposure_svc.compose(posicoes, contas_rf)

    # DUAS grandezas, não uma. `rf_classe` é o PESO da classe: um ETF de renda fixa vale o
    # que vale, então as posições do Ghostfolio entram. O PATRIMÔNIO é outra pergunta —
    # ali elas não podem entrar de novo, porque já estão na bolsa. Somar as duas coisas
    # contava o mesmo dinheiro duas vezes e inflava o alvo em R$ de todas as classes.
    rf_classe = composicao["by_class"].get(RENDA_FIXA, 0.0)

    held = {p.ticker: p.value for p in portfolio.positions}
    legacy_in_total = bool(prefs.get("legacy_in_total", True))
    aligned = aligned_value_by_class(held, all_baskets, targets)
    # Com o legado na base, o patrimônio é o que a composição já somou — cada posição e
    # cada conta uma vez. Sem ele, a base é só o capital alinhado de bolsa, e aí a classe
    # renda fixa precisa entrar INTEIRA: nada dela sobrevive ao filtro do alinhado, porque
    # a cesta de RENDA_FIXA é de tags de indexador e não de tickers. O `!= RENDA_FIXA`
    # explícito é o que torna a não-dupla-contagem verdadeira por construção, e não por
    # coincidência de nomenclatura.
    patrimonio = (
        composicao["total"]
        if legacy_in_total
        else sum(v for c, v in aligned.items() if c != RENDA_FIXA) + rf_classe
    )
    total_after = patrimonio + req.aporte
    rf_class_target = targets.get(RENDA_FIXA, 0.0) * total_after

    # Teto do aporte para o piso: do pedido, ou da preferência salva, ou 1.0 (prioridade
    # absoluta, o comportamento de sempre). `is not None` porque 0.0 é uma escolha.
    pref_share = prefs.get("reserve_floor_share")
    floor_share = (
        req.reserve_floor_share
        if req.reserve_floor_share is not None
        else (1.0 if pref_share is None else float(pref_share))
    )
    # Déficit das classes de bolsa pela MESMA fórmula do alocador: é contra ele que a renda
    # fixa disputa a sobra do aporte, em vez de pré-empregá-la.
    needs_rv = class_needs(aligned, targets, total_after, baskets)

    split = cascade.split_aporte(
        req.aporte,
        floor["deficit"],
        rf_class_target,
        rf_classe,
        floor_share=floor_share,
        rv_need=sum(needs_rv.values()),
    )
    aporte_rv = split["aporte_rv"]

    # 7) alocação do aporte de RENDA VARIÁVEL (após o pré-corte da reserva).
    # Lote conforme a preferência: 'fracionario' compra por unidade; 'integral' respeita
    # o lote real da B3 (ações = 100; FII/ETF/BDR = 1).
    lot_mode = prefs.get("lot_mode") or "integral"
    lots = {a.ticker: (1 if lot_mode == "fracionario" else a.lot_size) for a in assets}
    # O alocador NÃO recompõe a base: recebe o patrimônio resultante já calculado acima.
    # Enquanto ele refazia a conta com os pedaços que chegavam, somava só o `aporte_rv` e
    # chegava a um patrimônio menor exatamente pelo que a cascata tinha desviado para a
    # renda fixa — o dinheiro sumia da carteira resultante no caminho entre a rota e o
    # motor, e as classes recebiam orçamento contra alvos encolhidos.
    unallocated = allocate(
        aporte_rv, ranking, portfolio, prices, lots, targets, baskets,
        min_ticket=req.min_ticket, total_after=total_after,
    )

    # 7b) o pedaço da renda fixa que é COTA. Segunda chamada ao MESMO alocador, num mundo
    # de uma classe só — reusa déficit dentro da cesta, lote, ticket mínimo e troco sem
    # nenhum motor novo.
    #
    # A renda fixa NUNCA entra na mesma chamada da bolsa: o troco de lote atravessaria a
    # linha que a cascata acabou de traçar, e o plano diria "R$ X para o peso da classe"
    # enquanto gastava parte disso em FII. A frase é sobre dinheiro real.
    rateio_rf: dict[str, float] = {}
    rf_atual_pre: dict[str, float] = {}
    orc_rf_tickers = 0.0
    if split["rf_total"] > 0 and (rf_tags or rf_tickers):
        db_rf = get_db()
        tags_conta_pre = await labels_repo.assignments_by_subject(db_rf, "indexer", "fi_account")
        tags_ticker_pre = await labels_repo.assignments_by_subject(db_rf, "indexer", "ticker")
        rf_atual_pre = indexers_svc.value_by_indexer(
            contas_rf,
            tags_conta_pre,
            [
                {"ticker": p.ticker, "value": p.value}
                for p in portfolio.positions
                if p.asset_class == RENDA_FIXA
            ],
            tags_ticker_pre,
            basket_tickers=rf_tickers,
        )
        # UM rateio sobre a cesta inteira: os dois tipos disputam pela mesma régua. Só
        # depois o resultado é partido pelo tipo.
        rateio_rf = indexers_svc.basket_deficits(
            {**rf_tags, **rf_tickers}, rf_atual_pre, split["rf_total"]
        )
        orc_rf_tickers = from_cents(
            sum(to_cents(v) for c, v in rateio_rf.items() if c in rf_tickers)
        )

    if orc_rf_tickers > 0:
        held_rf = sum(held.get(t, 0.0) for t in rf_tickers)
        allocate(
            orc_rf_tickers, ranking, portfolio, prices, lots,
            {RENDA_FIXA: 1.0}, {RENDA_FIXA: rf_tickers},
            min_ticket=req.min_ticket,
            # `held + orçamento` faz `class_needs` devolver EXATAMENTE o orçamento: a
            # classe é 100% de si mesma, então não há renormalização nem sobra.
            total_after=held_rf + orc_rf_tickers,
        )

    # A cesta de renda fixa tem tags e tickers; o alocador só viu os tickers e renormalizou
    # entre eles. Reescrevemos a visão com os pesos VERDADEIROS e o denominador da classe
    # inteira — senão a linha do ranking diria "100% da cesta" para um ETF que o usuário pôs
    # em 30%, e a frase de "p.p. abaixo do alvo" sairia de um alvo inventado.
    if rf_tickers:
        cesta_rf = all_baskets.get(RENDA_FIXA) or {}
        peso_rf = sum(cesta_rf.values()) or 1.0
        valor_classe = rf_classe + split["rf_total"]
        for item in ranking:
            if item.ticker not in rf_tickers:
                continue
            alvo = float(cesta_rf.get(item.ticker, 0.0)) / peso_rf
            atual_item = held.get(item.ticker, 0.0)
            depois = atual_item + (item.suggested.invested_exact if item.suggested else 0.0)
            item.basket_target_pct = round(alvo, 6)
            item.basket_current_pct = round(atual_item / rf_classe, 6) if rf_classe > 0 else 0.0
            item.basket_after_pct = round(depois / valor_classe, 6) if valor_classe > 0 else 0.0
            item.basket_gap_brl = round(alvo * valor_classe - atual_item, 2)

    # mesma conta de necessidade do alocador — a explicação não pode divergir do motor
    at_target = {c for c, n in needs_rv.items() if n <= 0}
    # A renda fixa não passa por `needs_rv` (o alocador da bolsa nunca a vê), mas seus
    # tickers estão no mesmo ranking. Sem isto, um ETF de renda fixa numa classe já no peso
    # sairia com "não coube neste aporte" — culpando o lote por uma decisão da cascata.
    if cascade.rf_gap(rf_class_target, rf_classe, total_after)["brl"] <= 0:
        at_target.add(RENDA_FIXA)
    for item in ranking:
        item.reasons = _plan_reasons(item, at_target)

    # Gap = o que ainda falta comprar depois deste aporte, somado sobre as classes que
    # seguem abaixo do alvo. Mesma conta de necessidade do alocador, medida DEPOIS da
    # compra: é o buraco que sobra, não o que existia antes de aportar.
    valor_apos = {
        c: aligned.get(c, 0.0)
        + sum(
            (r.suggested.invested_exact if r.suggested else 0.0)
            for r in ranking
            if r.asset_class == c
        )
        for c in baskets
    }
    gap_restante = sum(
        max(0.0, targets.get(c, 0.0) * total_after - valor_apos[c]) for c in baskets
    )
    legacy = legacy_svc.summarize(
        [p.model_dump() for p in portfolio.positions], gap_restante, all_baskets, targets
    )

    # 8) parcela de renda fixa, item a item da cesta. A TAG vira instrução em R$ com a
    # conta sugerida para o lançamento (a compra é manual e aceita qualquer valor); o
    # TICKER vira cotas, preço e lote, porque essa se executa na corretora como qualquer
    # outra compra.
    fixed_income_suggestion = None
    if targets.get(RENDA_FIXA, 0.0) > 0 or floor_nominal > 0:
        gap = cascade.rf_gap(rf_class_target, rf_classe, total_after)
        by_indexer: list[IndexerAllocation] = []
        if split["rf_total"] > 0:
            db = get_db()
            tags_conta = await labels_repo.assignments_by_subject(db, "indexer", "fi_account")
            cesta = all_baskets.get(RENDA_FIXA) or {}
            atual = rf_atual_pre if cesta else {}
            # O que os tickers de fato consumiram, somado dos CENTAVOS já arredondados de
            # cada compra — e não do orçamento antes do lote. É o que faz a soma das linhas
            # do cartão bater com o dinheiro que sai da conta.
            por_ticker = {r.ticker: r for r in ranking}
            comprado: dict[str, float] = {}
            for t in rf_tickers:
                r = por_ticker.get(t)
                if r and r.suggested:
                    comprado[t] = r.suggested.invested_exact
            gasto_tickers = from_cents(sum(to_cents(v) for v in comprado.values()))
            # O troco de lote da renda fixa NÃO volta para a bolsa: fica na classe, e o
            # item que aceita qualquer valor sem lote é a conta. R$ 1,60 é um depósito
            # perfeitamente executável — infinitamente melhor que "não alocado".
            sobra_rf = from_cents(to_cents(orc_rf_tickers) - to_cents(gasto_tickers))
            orc_tags = from_cents(
                to_cents(split["rf_total"]) - to_cents(orc_rf_tickers) + to_cents(sobra_rf)
            )
            if rf_tags and orc_tags > 0:
                rateio_tags = indexers_svc.basket_deficits(rf_tags, atual, orc_tags)
            elif not cesta:
                # Sem cesta definida, a instrução é o total: dividir por tag exigiria um
                # alvo que o usuário não deu, e inventá-lo seria pior que não dividir.
                rateio_tags = {NO_INDEXER_CODE: split["rf_total"]}
            else:
                # Cesta 100% de tickers: o troco fica órfão e vai honestamente para a
                # sobra do aporte, em vez de atravessar a cascata.
                rateio_tags = {}
                if sobra_rf > 0:
                    unallocated = from_cents(to_cents(unallocated) + to_cents(sobra_rf))

            nomes = {r["code"]: r["name"] for r in await labels_repo.list_labels(db, "indexer")}
            nomes[NO_INDEXER_CODE] = NO_INDEXER_NAME
            # conta sugerida por tag: a de maior saldo que já tem aquele indexador — é
            # onde o dinheiro provavelmente vai, e evita redigitar o que o app já sabe.
            conta_da_tag: dict[str, dict] = {}
            for acc in sorted(contas_rf, key=lambda a: a["balance"], reverse=True):
                for tag in tags_conta.get(str(acc["id"]), []):
                    conta_da_tag.setdefault(tag["code"], acc)

            peso_total = sum(cesta.values()) or 1.0
            itens = {**rateio_tags, **comprado}
            for code, amount in sorted(itens.items(), key=lambda kv: kv[1], reverse=True):
                r = por_ticker.get(code) if code in rf_tickers else None
                acc = conta_da_tag.get(code) if r is None else None
                by_indexer.append(
                    IndexerAllocation(
                        code=code,
                        name=(r.name or code) if r else nomes.get(code, code),
                        amount=amount,
                        current_value=atual.get(code, 0.0),
                        target_pct=round(float(cesta.get(code, 0.0)) / peso_total, 6),
                        account_id=acc["id"] if acc else None,
                        account_name=acc["name"] if acc else None,
                        kind="ticker" if r else "indexer",
                        ticker=code if r else None,
                        price=r.suggested.price if r and r.suggested else None,
                        shares=r.suggested.shares if r and r.suggested else 0,
                        lot_size=r.suggested.lot_size if r and r.suggested else 1,
                    )
                )

        teto_txt = f"máximo de {floor_share * 100:.0f}% do aporte"
        if split["rf_total"] > 0:
            partes = []
            if split["floor_directed"] > 0:
                piso_txt = f"{_brl(split['floor_directed'])} para o piso da reserva"
                # sem isto, cobrir R$ 1.000 de um déficit de R$ 9.501 pareceria erro de conta
                if split["floor_capped"]:
                    piso_txt += f" ({teto_txt})"
                partes.append(piso_txt)
            if split["rf_directed"] > 0:
                partes.append(f"{_brl(split['rf_directed'])} para o peso da classe")
            nota = " e ".join(partes) + "."
        elif split["floor_capped"]:
            # só se chega aqui com o teto em 0% e o piso em déficit: o silêncio esconderia
            # uma decisão de não cobrir o piso
            nota = f"Nada para o piso da reserva: {teto_txt}."
        elif gap["brl"] <= 0:
            # Acima do alvo é uma carteira saudável, não um erro: nada de aviso.
            nota = "Renda fixa no alvo ou acima — o aporte inteiro vai para a renda variável."
            # Mas um ticker de renda fixa longe do peso DENTRO da cesta some sem explicação
            # aqui: o usuário deu 40% ao IMAB11, não vê cota nenhuma e conclui que o app
            # ignorou o que ele pediu. A causa é a classe estar acima do alvo, e a solução
            # é trocar de aplicação — que é decisão dele, porque o Pomar não sugere venda.
            atrasado = max(
                (r for r in ranking if r.ticker in rf_tickers and (r.basket_gap_brl or 0) > 0),
                key=lambda r: r.basket_gap_brl or 0.0,
                default=None,
            )
            if atrasado is not None:
                nota += (
                    f" Dentro da classe, {atrasado.ticker} está "
                    f"{_brl(atrasado.basket_gap_brl or 0.0)} abaixo do peso que você deu: "
                    "isso se resolve trocando de aplicação, não com aporte novo."
                )
        else:
            nota = "Sem sobra para a renda fixa neste aporte."

        colocado = from_cents(sum(to_cents(i.amount) for i in by_indexer))
        fixed_income_suggestion = FixedIncomeSuggestion(
            directed_now=colocado if by_indexer else split["rf_total"],
            floor_part=split["floor_directed"],
            weight_part=split["rf_directed"],
            current_value=rf_classe,
            target_amount=round(rf_class_target, 2),
            gap_brl=gap["brl"],
            gap_pp=gap["pp"],
            by_indexer=by_indexer,
            note=nota,
        )

    # 9) status do piso (só quando existe um piso configurado — sem piso, sem card)
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
        # Frações do PATRIMÔNIO INTEIRO — o mesmo denominador de `targets_by_class`, e o
        # mesmo da aba Carteira. `portfolio.allocations.by_class` são frações só da renda
        # variável (a soma dos pesos que o Ghostfolio dá a cada posição): publicá-las aqui
        # fazia o card comparar 82% de uma coisa com 0% de outra, e sumir com a renda fixa.
        current_by_class=_fracoes(composicao["by_class"], composicao["total"]),
        ranking=suggested + others,
        unallocated=unallocated,
        reserve=reserve,
        fixed_income=fixed_income_suggestion,
        legacy=LegacySummary(**legacy) if legacy else None,
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
