"""Modelos do plano de aporte.

O Pomar não pontua ativos: ele REBALANCEIA. O usuário define a meta por classe
(STOCK/FII/ETF/BDR) e, dentro de cada classe, a composição-alvo por ativo (a "cesta").
O plano responde a uma pergunta só: com este dinheiro, o que comprar para chegar mais
perto da carteira que o próprio usuário definiu?
"""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from app.models.market import Asset

# Classes que o alocador sabe COMPRAR: têm cotação e lote, e a resposta é "quantas cotas".
INVESTABLE_CLASSES = ("STOCK", "FII", "ETF", "BDR")

# A carteira alvo inteira — o nível 1 da árvore de buckets. `RENDA_FIXA` é uma classe como
# as outras para efeito de peso e de déficit, mas a compra é manual e feita fora do app, e
# os itens da cesta dela são TAGS DE INDEXADOR (CDI, IPCA, LCI…), não tickers com preço.
# Por isso ela fica de fora de INVESTABLE_CLASSES: pedir "quantas cotas de CDI comprar" não
# é uma pergunta com resposta.
RENDA_FIXA = "RENDA_FIXA"
ALLOCATION_CLASSES = (*INVESTABLE_CLASSES, RENDA_FIXA)

# Rótulo em português de cada classe — fonte única, para as telas não divergirem.
CLASS_LABEL = {
    "STOCK": "Ações",
    "FII": "FIIs",
    "ETF": "ETFs",
    "BDR": "BDRs",
    RENDA_FIXA: "Renda fixa",
    "UNKNOWN": "Outros",
}


class SuggestedBuy(BaseModel):
    """Quanto comprar de um ativo — com a aritmética completa, auditável."""

    target_amount: float = Field(..., description="Valor-alvo a aportar neste ativo (BRL).")
    price: Optional[float] = Field(None, description="Cotação usada no cálculo (BRL).")
    shares: int = Field(0, description="Número inteiro de cotas/ações sugerido.")
    invested_exact: float = Field(0.0, description="shares * price — gasto real estimado.")
    lot_size: int = Field(1, description="Tamanho do lote considerado.")
    lot_note: Optional[str] = Field(None, description="Observação sobre lote/arredondamento.")


class PlanAsset(BaseModel):
    """Um ativo da carteira alvo dentro do plano.

    Só `ticker` é obrigatório: planos antigos, persistidos com outro formato, precisam
    continuar sendo lidos por GET /plan/latest (campo que falta vira default).
    """

    ticker: str
    name: Optional[str] = None
    asset_class: str = "UNKNOWN"
    sector: Optional[str] = None
    price: Optional[float] = None
    dividend_yield: Optional[float] = Field(None, description="DY anual em fração (0..1).")

    # Posição do ativo DENTRO da cesta da sua classe (frações 0..1, não percentuais).
    basket_target_pct: Optional[float] = Field(
        None, description="Peso-alvo do ativo na cesta da classe, definido pelo usuário."
    )
    basket_current_pct: Optional[float] = Field(
        None, description="Peso atual do ativo na cesta (valor dele ÷ valor da cesta hoje)."
    )
    basket_after_pct: Optional[float] = Field(
        None, description="Peso do ativo na cesta DEPOIS das compras sugeridas."
    )
    basket_gap_brl: Optional[float] = Field(
        None,
        description="Quanto falta em R$ para o peso-alvo, medido sobre a cesta já com o "
        "aporte (positivo = abaixo do alvo; é isto que determina a compra).",
    )

    # Preço-teto de Bazin — independente do rebalanceamento: um ativo pode estar no peso-alvo
    # e ainda assim barato (e vice-versa). É o gatilho para antecipar compra por conta própria.
    bazin_ceiling_price: Optional[float] = Field(
        None, description="Preço-teto de Bazin em BRL (dividendo médio ÷ DY-alvo). None se indisponível."
    )
    bazin_below_ceiling: Optional[bool] = Field(
        None, description="True se o preço atual está abaixo do teto (zona de compra)."
    )
    bazin_margin: Optional[float] = Field(
        None, description="Margem sobre o teto em [-1,1] (positivo = comprando com desconto)."
    )

    risk_level: str = Field("verde", description="Selo de risco factual: verde | amarelo | vermelho.")
    red_flags: List[str] = Field(
        default_factory=list, description="Pontos de atenção (por que olhar duas vezes)."
    )
    reasons: List[str] = Field(
        default_factory=list, description="Frases curtas explicando a sugestão (ou a ausência dela)."
    )
    suggested: Optional[SuggestedBuy] = None


class ReserveSuggestion(BaseModel):
    """Status do PISO da reserva e quanto deste aporte ele consome.

    Os cinco primeiros campos mantêm os nomes que sempre tiveram porque o PAPEL deles não
    mudou — alvo em R$, quanto existe, quanto falta, quanto está preenchido, quanto vai
    agora. O que mudou foi a definição do alvo: era `fração × patrimônio` e passou a ser o
    piso corrigido. Todos têm default para que `GET /plan/latest` continue conseguindo ler
    os planos gravados antes desta mudança.
    """

    target_amount: float = Field(0.0, description="Piso corrigido — o alvo em BRL.")
    current_amount: float = Field(
        0.0,
        description="Reserva LÍQUIDA (BRL): só contas que contam na carteira, de propósito "
        "'investment' e com resgate imediato.",
    )
    gap: float = Field(0.0, description="Déficit do piso (BRL).")
    pct_filled: float = Field(0.0, description="Fração do piso já preenchida (0..1).")
    directed_now: float = Field(0.0, description="Quanto deste aporte vai para a reserva (BRL).")
    benchmark_cdi_annual: Optional[float] = Field(None, description="CDI anualizado (fração), referência.")
    floor_nominal: float = Field(0.0, description="Piso como o usuário digitou, sem correção.")
    floor_date: Optional[str] = Field(None, description="Data-base do piso (ISO).")
    floor_index: str = Field("none", description="'none' | 'ipca'.")
    floor_index_available: bool = Field(
        True, description="False quando o IPCA não veio e o piso exibido é o nominal."
    )
    note: str = Field("O piso da reserva é coberto antes de qualquer compra.")


class IndexerAllocation(BaseModel):
    """Quanto do aporte vai para UMA instrução de renda fixa.

    Três tipos, uma lista só. Duas listas separadas obrigariam o leitor a re-somar as
    partes para saber quanto foi para a classe — que é a única pergunta que o cartão
    responde.

    * `floor` — o piso da reserva. Um valor, a lançar numa conta de resgate imediato; a
      escolha da conta é do usuário, então não vem nem indexador nem conta sugerida. É
      sempre a primeira da lista: é o primeiro degrau da cascata.
    * `indexer` — uma tag da cesta (CDI, IPCA, LCI). Cumpre-se lançando dinheiro numa
      conta, em qualquer valor, e o app aponta a que já tem aquela tag.
    * `ticker` — um ETF de renda fixa. Cumpre-se comprando cotas, com lote e ticket mínimo.
    """

    code: str
    name: str
    amount: float = Field(
        0.0,
        description="Valor a aplicar neste item (BRL). Num ticker é `cotas × preço` — o "
        "gasto REAL depois do lote, para a soma do cartão bater com o que sai da conta.",
    )
    current_value: float = Field(0.0, description="Quanto já existe neste item (BRL).")
    target_pct: float = Field(0.0, description="Peso-alvo dentro da classe (0..1).")
    account_id: Optional[int] = Field(
        None, description="Conta sugerida para o lançamento (só quando kind='indexer')."
    )
    account_name: Optional[str] = None

    # Campos do item que é TICKER. Todos com default: `GET /plan/latest` desserializa
    # planos gravados quando a cesta de renda fixa só tinha tags.
    kind: str = Field(
        "indexer",
        description="'floor' = piso, lançar em conta de resgate imediato (a escolha é do "
        "usuário); 'indexer' = lançar na conta sugerida; 'ticker' = comprar cotas.",
    )
    ticker: Optional[str] = Field(None, description="Ticker a comprar (só em kind='ticker').")
    price: Optional[float] = Field(None, description="Cotação usada no cálculo (BRL).")
    shares: int = Field(0, description="Cotas inteiras a comprar.")
    lot_size: int = Field(1, description="Tamanho do lote considerado.")


class FixedIncomeSuggestion(BaseModel):
    """A parcela de renda fixa do aporte — o primeiro degrau da cascata.

    A compra de renda fixa é manual e feita fora do app, então aqui não há quantidade de
    cotas: a saída é uma INSTRUÇÃO em reais, com o atalho para lançar o novo saldo na
    conta sugerida (o app não pede que ninguém redigite o que já sabe).
    """

    directed_now: float = Field(0.0, description="Total do aporte que vai para a renda fixa.")
    floor_part: float = Field(0.0, description="Parte que cobre o PISO da reserva (BRL).")
    weight_part: float = Field(0.0, description="Parte que cobre o PESO da classe (BRL).")
    current_value: float = Field(0.0, description="Valor atual da classe RENDA_FIXA (BRL).")
    target_amount: float = Field(0.0, description="Alvo da classe pelo peso (BRL).")
    gap_brl: float = Field(0.0, description="Gap da classe em BRL (0 quando está acima do alvo).")
    gap_pp: float = Field(0.0, description="O mesmo gap em pontos percentuais do patrimônio.")
    by_indexer: List[IndexerAllocation] = Field(default_factory=list)
    note: Optional[str] = Field(None, description="Uma linha factual sobre o que fazer.")


class LegacySummary(BaseModel):
    """Quanto está parado em ativos fora da carteira alvo, e o que isso cobriria.

    É ARITMÉTICA, não sugestão de venda: o app não recomenda vender nada. O que ele
    responde é quanto do gap atual está em capital que já não segue a estratégia — número
    que o usuário não consegue estimar de cabeça.
    """

    value: float = Field(0.0, description="Valor em ativos fora do alvo (BRL).")
    tickers: List[str] = Field(default_factory=list)
    gap: float = Field(0.0, description="Quanto falta comprar para atingir os alvos (BRL).")
    gap_coverage: Optional[float] = Field(
        None,
        description="Fração do gap que o legado cobriria (0..1+). None quando não há gap.",
    )


class PlanResponse(BaseModel):
    aporte: float
    currency: str = "BRL"
    as_of: str
    targets_by_class: Dict[str, float] = Field(default_factory=dict)
    current_by_class: Dict[str, float] = Field(default_factory=dict)
    ranking: List[PlanAsset] = Field(default_factory=list)
    unallocated: float = Field(0.0, description="Sobra do aporte não alocada (BRL).")
    reserve: Optional[ReserveSuggestion] = Field(
        None, description="Status do piso da reserva (quando há um piso configurado)."
    )
    fixed_income: Optional[FixedIncomeSuggestion] = Field(
        None, description="Parcela de renda fixa do aporte (quando a classe tem peso ou piso)."
    )
    legacy: Optional[LegacySummary] = Field(
        None, description="Ativos fora da carteira alvo (quando existem)."
    )
    classes_applied: List[str] = Field(
        default_factory=list, description="Classes marcadas que tinham composição e entraram no plano."
    )
    classes_skipped: List[str] = Field(
        default_factory=list, description="Classes marcadas SEM composição definida — puladas."
    )
    warnings: List[str] = Field(default_factory=list)
    plan_id: Optional[int] = Field(None, description="Id do plano persistido (plan_history).")
    created_at: Optional[str] = Field(None, description="Quando o plano foi gerado (planos salvos).")


class PlanSummary(BaseModel):
    """Resumo de um plano salvo (lista 'Planos anteriores')."""

    id: int
    created_at: Optional[str] = None
    aporte: Optional[float] = None
    suggested_count: Optional[int] = None


class AssetAnalysis(BaseModel):
    """Leitura FACTUAL de um ativo — sem nota, sem ranking, sem estratégia.

    Números calculados a partir das fontes (preço-teto de Bazin, consistência e
    crescimento dos proventos, payout) e os alertas que decorrem deles.
    """

    ticker: str
    name: Optional[str] = None
    asset_class: str = "UNKNOWN"
    sector: Optional[str] = None
    price: Optional[float] = None
    dividend_yield: Optional[float] = None
    dividend_yield_net: Optional[float] = Field(None, description="DY líquido (JCP ×0,85).")
    bazin_ceiling_price: Optional[float] = None
    bazin_below_ceiling: Optional[bool] = None
    bazin_margin: Optional[float] = None
    bazin_target_yield: float = Field(0.06, description="DY-alvo usado no preço-teto.")
    dividend_consistency: Optional[float] = Field(
        None, description="Anos pagos ÷ anos analisados, penalizando cortes fortes (0..1)."
    )
    dividend_cagr: Optional[float] = Field(None, description="Crescimento anual dos proventos (fração).")
    payout_ratio: Optional[float] = Field(None, description="Provento médio ÷ LPA (fração).")
    risk_level: str = "verde"
    red_flags: List[str] = Field(default_factory=list)
    highlights: List[str] = Field(default_factory=list, description="Pontos factuais favoráveis.")


class AssetDetailResponse(BaseModel):
    """Detalhe de um ativo: dados crus (fundamentos, proventos) + a leitura factual."""

    asset: Asset
    analysis: AssetAnalysis


class PlanRequest(BaseModel):
    aporte: float = Field(..., gt=0, description="Quanto você tem para investir hoje (BRL).")
    classes: Optional[List[str]] = Field(
        None,
        description="Classes que devem receber este aporte (STOCK/FII/ETF/BDR). "
        "Omitido = todas. Lista vazia é erro (não há o que planejar).",
    )
    targets: Optional[Dict[str, float]] = Field(
        None, description="Alvos de alocação por classe (0..1). Se omitido, usa o default."
    )
    min_ticket: float = Field(
        100.0, ge=0, description="Valor mínimo para ABRIR posição em um ativo (BRL)."
    )
    reserve_target: Optional[float] = Field(
        None,
        ge=0,
        le=1,
        deprecated=True,
        description="APOSENTADO e IGNORADO: a reserva deixou de ser uma fração do patrimônio "
        "e virou um piso em R$ dentro da classe RENDA_FIXA (preferências).",
    )
    reserve_current: Optional[float] = Field(
        None,
        ge=0,
        description="Sobrepõe a reserva LÍQUIDA lida do rastreador de renda fixa (BRL).",
    )
    reserve_floor: Optional[float] = Field(
        None, ge=0, description="Sobrepõe o piso da reserva das preferências (BRL)."
    )
    reserve_floor_share: Optional[float] = Field(
        None,
        ge=0,
        le=1,
        description="Teto do aporte para o PISO da reserva (0..1). Omitido usa a "
        "preferência salva; 1 é prioridade absoluta.",
    )
    allow_empty_portfolio: bool = Field(
        False,
        description="Permite gerar plano SEM conseguir ler a carteira (fail-open explícito). "
        "Por padrão o plano é abortado: alocar dinheiro real sobre carteira vazia produz "
        "sugestões materialmente erradas.",
    )

    @field_validator("classes")
    @classmethod
    def _classes_validas(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return None
        out: List[str] = []
        for raw in v:
            c = (raw or "").strip().upper()
            if c not in ALLOCATION_CLASSES:
                raise ValueError(f"classe '{raw}' inválida; use {', '.join(ALLOCATION_CLASSES)}.")
            if c not in out:
                out.append(c)
        if not out:
            raise ValueError("marque ao menos uma classe para receber o aporte.")
        return out
