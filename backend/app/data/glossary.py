"""Glossário: a FONTE ÚNICA das explicações de cada número exibido.

O frontend busca isto uma vez (GET /api/glossary) e resolve os tooltips pela `key`.
Define o CÁLCULO e a FONTE de cada número, não o conceito de mercado. O campo `source` é o
coração do verbete: a pergunta real é como ESTE app chegou neste número.
"""
from __future__ import annotations

from typing import Dict

GLOSSARY: Dict[str, Dict[str, str]] = {
    "pvp": {
        "label": "P/VP",
        "definition": "Preço sobre Valor Patrimonial. Compara o preço do ativo com o valor "
        "contábil do patrimônio dele. Abaixo de 1: preço abaixo do valor contábil do patrimônio."
        "",
        "source": "Fundamentus (indicador P/VP)",
        "interpretation": "Comparável só entre pares do mesmo setor.",
    },
    "pl": {
        "label": "P/L",
        "definition": "Preço sobre Lucro. Anos de lucro atual para amortizar o preço da ação. Não se aplica a FIIs.",
        "source": "Fundamentus (indicador P/L)",
        "interpretation": "Menor costuma indicar ação mais barata frente ao lucro — mas lucro "
        "baixo/negativo distorce o número.",
    },
    "div_yield": {
        "label": "Dividend Yield",
        "definition": "Soma dos proventos pagos nos últimos 365 dias (por data de pagamento) "
        "dividido pelo preço atual. Renda bruta por real investido.",
        "source": "calculado: proventos dos últimos 365 dias (StatusInvest) ÷ preço",
        "interpretation": "Maior é melhor para renda, mas yields muito altos podem ser "
        "pontuais, e yields não recorrentes são penalizados no score.",
    },
    "net_yield": {
        "label": "Dividend Yield líquido",
        "definition": "Como o Dividend Yield, mas após o imposto: JCP sofre 15% de IR na fonte "
        "(×0,85); dividendos de ações e rendimentos de FII são isentos para pessoa física.",
        "source": "calculado: (dividendos + 0,85×JCP) dos últimos 365 dias ÷ preço",
        "interpretation": "Para bancos que pagam muito via JCP (ITUB4, BBAS4), o líquido fica "
        "abaixo do bruto. Use o líquido para planejar quanto vai realmente receber.",
    },
    "bazin_ceiling": {
        "label": "Margem Bazin (preço-teto)",
        "definition": "Método de Décio Bazin: o preço-teto é o dividendo médio anual "
        "dividido pelo DY-alvo (6% por padrão). Comprar abaixo desse teto garante um yield "
        "mínimo. A margem mostra o quanto o preço atual está abaixo (positivo) ou acima do teto.",
        "source": "calculado: preço-teto = média de proventos da janela de 5 anos (ano sem pagar "
        "conta como zero) ÷ DY-alvo; margem = (teto − preço) ÷ teto",
        "interpretation": "Margem positiva = comprando abaixo do teto (bom). Negativa = caro "
        "frente ao histórico — e no score a margem negativa vale zero, mesmo que os pares "
        "estejam piores. O DY-alvo é configurável (ou atrelado à Selic).",
    },
    "bazin_ceiling_price": {
        "label": "Preço-teto (Bazin)",
        "definition": "O preço máximo a pagar pela ação, em reais, para garantir o DY-alvo "
        "(6% por padrão), usando a média dos proventos da janela de 5 anos — anos sem pagamento "
        "contam como zero, então pagadora irregular tem teto menor. Comprar abaixo dele dá "
        "margem de segurança de renda.",
        "source": "calculado: média de proventos (janela de 5 anos, zeros incluídos) ÷ DY-alvo",
        "interpretation": "Abaixo do teto: zona de compra pelo método Bazin. Acima: yield esperado "
        "abaixo da meta.",
    },
    "yield_on_cost": {
        "label": "Yield on Cost (YoC)",
        "definition": "Quanto a posição rende em proventos sobre o preço médio de compra, não sobre o preço de "
        "mercado atual. Em acumulação longa sobe conforme o provento cresce.",
        "source": "calculado: provento anual por cota ÷ preço médio de compra (Ghostfolio)",
        "interpretation": "YoC acima do yield de mercado significa que o preço subiu desde a sua "
        "compra — sua renda sobre o custo é maior que a de quem compra hoje.",
    },
    "dividend_consistency": {
        "label": "Consistência de dividendos",
        "definition": "Há quantos dos últimos anos o ativo pagou dividendos de forma recorrente, "
        "com penalidade para CORTES fortes (queda de mais de 50% de um ano para o outro). "
        "Mede regularidade de pagamento, não tamanho do provento.",
        "source": "calculado: anos pagos ÷ anos analisados, ×0,75 por corte >50% (StatusInvest)",
        "interpretation": "Perto de 1 = paga quase todo ano sem cortes bruscos. Baixo = renda "
        "irregular ou em queda, menos confiável para viver de dividendos.",
    },
    "rebalance_gap": {
        "label": "Rebalanceamento",
        "definition": "O quanto este ativo/classe está abaixo do alvo que você definiu para a "
        "carteira. Comprar o que está sub-alocado aproxima a carteira da meta.",
        "source": "calculado: peso-alvo − peso-atual (carteira do Ghostfolio vs seus alvos)",
        "interpretation": "Quanto mais abaixo do alvo, maior a prioridade de aporte. A % de cada "
        "item é sobre a carteira inteira: meta da classe × peso dentro da classe. Em renda "
        "fixa o item é o indexador, não um ticker.",
    },
    "suggested_amount": {
        "label": "Valor sugerido",
        "definition": "Quanto do seu aporte de hoje o plano sugere colocar neste ativo, já "
        "arredondado para um número inteiro de cotas pelo preço atual.",
        "source": "calculado: aporte dividido entre as classes pelo que falta para a meta e, "
        "dentro da classe, pelo déficit de cada ativo até o peso-alvo — ajustado por lote",
        "interpretation": "Zero: o ativo já está no peso-alvo ou acima. A sobra de "
        "arredondamento aparece em \"não alocado\".",
    },
    "twr": {
        "label": "TWR",
        "definition": "Retorno ponderado pelo tempo. Neutraliza aportes e resgates, isolando "
        "o efeito das escolhas de alocação do efeito de quanto dinheiro entrou e quando.",
        "source": "calculado: retorno de cada semana encadeado multiplicativamente "
        "(Modified Dietz para ponderar o fluxo dentro da semana)",
        "interpretation": "É a única série da curva comparável a um índice, porque índice não "
        "tem aporte. O XIRR ao lado responde outra pergunta: quanto o SEU dinheiro rendeu.",
    },
    "min_ticket": {
        "label": "Ticket mínimo",
        "definition": "Valor mínimo para ABRIR uma posição nova. Reforço de posição que já "
        "existe não depende dele.",
        "source": "configuração (preferências)",
        "interpretation": "Serve para não pulverizar o aporte em posições pequenas demais para "
        "justificar a corretagem e o acompanhamento. Não confundir com o piso da reserva, que "
        "é outra coisa e fica na aba Reserva.",
    },
    "reserve_floor_share": {
        "label": "Máximo do aporte para o piso",
        "definition": "Fatia máxima do aporte que pode ir para o PISO da reserva. Em 50%, "
        "um aporte de R$ 2.000 manda no máximo R$ 1.000 para o piso, mesmo que falte mais.",
        "source": "configuração (preferências), aplicada ao primeiro degrau do aporte",
        "interpretation": "É teto, não cota: com o piso já composto não há déficit e o "
        "controle não faz nada. O que não vai para o piso disputa o aporte com as demais "
        "classes, e quem está mais defasado leva a maior fatia.",
    },
    "reserve_floor": {
        "label": "Piso da reserva",
        "definition": "O mínimo, em reais, que deve ficar em renda fixa de resgate imediato. "
        "Não é uma reserva separada: é um piso dentro da própria classe de renda fixa, e o "
        "alvo da classe é o maior entre o peso percentual e este piso.",
        "source": "configuração (preferências) + saldos das contas de resgate imediato que "
        "contam na carteira",
        "interpretation": "Aplicação com carência soma no peso da classe, mas não conta para "
        "o piso — o piso mede o dinheiro disponível hoje. Com a correção pelo IPCA ligada, "
        "o piso sobe mensalmente para não encolher em poder de compra.",
    },
    "liquid_reserve": {
        "label": "Reserva líquida",
        "definition": "Soma das contas que contam na carteira, com propósito de investimento "
        "e resgate imediato (D+0/D+1). É o disponível para saque hoje.",
        "source": "calculado: saldos do rastreador de renda fixa filtrados por liquidez",
        "interpretation": "Menor que o total de renda fixa sempre que houver CDB com carência, "
        "LCI/LCA travadas ou dinheiro reservado para outro fim (como a provisão de imposto).",
    },
    "fixed_income_yield": {
        "label": "Rendimento da reserva",
        "definition": "Taxa anualizada (base 252 dias úteis) de TODO o histórico da conta: cada "
        "intervalo entre dois saldos rende à sua própria taxa (método Modified Dietz, que pondera "
        "aportes e resgates pelo tempo aplicado) e os intervalos são encadeados. Aportar ou "
        "resgatar não move a taxa — só o rendimento do produto move.",
        "source": "calculado: lançamentos da conta (saldos, aportes, resgates) + CDI do Banco Central",
        "interpretation": "O IR retido num resgate sai do saldo e aparece aqui como rendimento "
        "menor. LCI e LCA são isentas, então comparar o rendimento delas com o CDI bruto "
        "subestima o que elas de fato entregam.",
    },
    "net_performance": {
        "label": "Retorno da posição",
        "definition": "Rentabilidade total líquida da posição desde a compra (valorização + "
        "proventos, conforme o Ghostfolio calcula), em percentual.",
        "source": "Ghostfolio (netPerformancePercent)",
        "interpretation": "Comparável ao CDI acumulado do mesmo período.",
    },
}


def get_glossary() -> Dict[str, Dict[str, str]]:
    return GLOSSARY
