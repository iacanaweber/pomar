"""Glossário: a FONTE ÚNICA das explicações de cada número exibido.

O frontend busca isto uma vez (GET /api/glossary) e resolve os tooltips pela `key`.
Linguagem acessível de propósito — o usuário não é especialista.
"""
from __future__ import annotations

from typing import Dict

GLOSSARY: Dict[str, Dict[str, str]] = {
    "pvp": {
        "label": "P/VP",
        "definition": "Preço sobre Valor Patrimonial. Compara o preço do ativo com o valor "
        "contábil do patrimônio dele. Abaixo de 1 sugere que o mercado paga menos do que o "
        "patrimônio 'vale no papel' — possível desconto.",
        "source": "Fundamentus (indicador P/VP)",
        "interpretation": "Quanto menor, mais 'barato' em relação ao patrimônio. Compare sempre "
        "com pares do mesmo setor.",
    },
    "pl": {
        "label": "P/L",
        "definition": "Preço sobre Lucro. Quantos anos de lucro atual seriam necessários para "
        "'pagar' o preço da ação. Não faz sentido para FIIs.",
        "source": "Fundamentus (indicador P/L)",
        "interpretation": "Menor costuma indicar ação mais barata frente ao lucro — mas lucro "
        "baixo/negativo distorce o número.",
    },
    "div_yield": {
        "label": "Dividend Yield",
        "definition": "Soma dos proventos pagos nos últimos 365 dias (por data de pagamento) "
        "dividido pelo preço atual. É a 'renda' BRUTA que o ativo gera por reais investidos.",
        "source": "calculado: proventos dos últimos 365 dias (StatusInvest) ÷ preço",
        "interpretation": "Maior é melhor para renda, mas yields muito altos podem ser "
        "pontuais (não se repetem) — por isso penalizamos os que parecem não recorrentes.",
    },
    "net_yield": {
        "label": "Dividend Yield líquido",
        "definition": "Como o Dividend Yield, mas após o imposto: JCP sofre 15% de IR na fonte "
        "(×0,85); dividendos de ações e rendimentos de FII são isentos para pessoa física. "
        "Mostra a renda que efetivamente cai na sua conta.",
        "source": "calculado: (dividendos + 0,85×JCP) dos últimos 365 dias ÷ preço",
        "interpretation": "Para bancos que pagam muito via JCP (ITUB4, BBAS4), o líquido fica "
        "abaixo do bruto. Use o líquido para planejar quanto vai realmente receber.",
    },
    "bazin_ceiling": {
        "label": "Margem Bazin (preço-teto)",
        "definition": "Método de Décio Bazin: o 'preço-teto' justo é o dividendo médio anual "
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
        "interpretation": "Se o preço atual está ABAIXO do teto, é zona de compra pelo método "
        "Bazin. Acima do teto, o yield esperado fica abaixo da sua meta.",
    },
    "yield_on_cost": {
        "label": "Yield on Cost (YoC)",
        "definition": "Quanto a posição rende em proventos sobre o PREÇO QUE VOCÊ PAGOU (preço "
        "médio), não sobre o preço de mercado atual. Para quem acumula por décadas, o YoC tende "
        "a crescer e mostra o 'rendimento do que você plantou'.",
        "source": "calculado: provento anual por cota ÷ preço médio de compra (Ghostfolio)",
        "interpretation": "YoC acima do yield de mercado significa que o preço subiu desde a sua "
        "compra — sua renda sobre o custo é maior que a de quem compra hoje.",
    },
    "dividend_consistency": {
        "label": "Consistência de dividendos",
        "definition": "Há quantos dos últimos anos o ativo pagou dividendos de forma recorrente, "
        "com penalidade para CORTES fortes (queda de mais de 50% de um ano para o outro). "
        "Recompensa pagadoras regulares (estilo Barsi/Bazin) e desconfia de proventos pontuais.",
        "source": "calculado: anos pagos ÷ anos analisados, ×0,75 por corte >50% (StatusInvest)",
        "interpretation": "Perto de 1 = paga quase todo ano sem cortes bruscos. Baixo = renda "
        "irregular ou em queda, menos confiável para viver de dividendos.",
    },
    "rebalance_gap": {
        "label": "Rebalanceamento",
        "definition": "O quanto este ativo/classe está abaixo do alvo que você definiu para a "
        "carteira. Comprar o que está sub-alocado aproxima a carteira da meta.",
        "source": "calculado: peso-alvo − peso-atual (carteira do Ghostfolio vs seus alvos)",
        "interpretation": "Quanto mais abaixo do alvo, maior a prioridade de aporte.",
    },
    "suggested_amount": {
        "label": "Valor sugerido",
        "definition": "Quanto do seu aporte de hoje o plano sugere colocar neste ativo, já "
        "arredondado para um número inteiro de cotas pelo preço atual.",
        "source": "calculado: aporte dividido entre as classes pelo que falta para a meta e, "
        "dentro da classe, pelo déficit de cada ativo até o peso-alvo — ajustado por lote",
        "interpretation": "Zero significa que o ativo já está no peso-alvo (ou acima) — não que "
        "ele seja ruim. A sobra de arredondamento aparece em 'não alocado'.",
    },
    "reserve_target": {
        "label": "Reserva-alvo",
        "definition": "A fração do seu patrimônio total (renda variável + reserva) que deve "
        "ficar em renda fixa/caixa. Disciplina Barsi: completar a reserva vem ANTES de comprar "
        "renda variável — o plano desvia parte do aporte para cá até o alvo ser atingido.",
        "source": "configuração (preferências) + saldo do rastreador de renda fixa",
        "interpretation": "Ex.: 10% = a cada aporte, a reserva é completada primeiro; o restante "
        "vai para as compras sugeridas.",
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
        "ele sobe alguns reais por mês para não encolher em poder de compra.",
    },
    "liquid_reserve": {
        "label": "Reserva líquida",
        "definition": "Soma das contas que contam na carteira, com propósito de investimento "
        "e resgate imediato (D+0/D+1). É o número que responde 'quanto eu tiro hoje'.",
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
        "interpretation": "~100% do CDI é o esperado para uma boa reserva líquida. Muito abaixo, "
        "considere trocar de produto. Atenção ao imposto: o IR retido num resgate sai do saldo e "
        "aparece aqui como rendimento menor.",
    },
    "net_performance": {
        "label": "Retorno da posição",
        "definition": "Rentabilidade total líquida da posição desde a compra (valorização + "
        "proventos, conforme o Ghostfolio calcula), em percentual.",
        "source": "Ghostfolio (netPerformancePercent)",
        "interpretation": "Compare com o CDI acumulado do mesmo período antes de concluir se "
        "valeu a pena — anos ruins de bolsa fazem parte do método de décadas.",
    },
}


def get_glossary() -> Dict[str, Dict[str, str]]:
    return GLOSSARY
