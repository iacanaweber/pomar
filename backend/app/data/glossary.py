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
    "graham": {
        "label": "Margem Graham",
        "definition": "Critério de valor de Benjamin Graham: uma ação 'barata' tende a ter "
        "P/L e P/VP baixos. A regra clássica diz que o produto P/L × P/VP deve ficar até 22,5 "
        "(equivale a P/L 15 e P/VP 1,5). Quanto menor o produto, maior a margem de segurança.",
        "source": "calculado: distância de P/L × P/VP (Fundamentus) ao teto 22,5 de Graham",
        "interpretation": "Produto bem abaixo de 22,5 sugere preço com desconto e margem de "
        "segurança; acima do teto, a margem é zero. Aplica-se a ações, não a FIIs.",
    },
    "graham_intrinsic": {
        "label": "Margem (Número de Graham)",
        "definition": "Valor intrínseco aproximado de Graham = √(22,5 × LPA × VPA), onde LPA é o "
        "lucro por ação e VPA o valor patrimonial por ação. A margem mostra o quanto o preço "
        "está abaixo (positivo) desse valor justo.",
        "source": "calculado: √(22,5 × LPA × VPA) vs preço (LPA/VPA do Fundamentus)",
        "interpretation": "Margem positiva = preço abaixo do valor intrínseco de Graham. Exige "
        "lucro e patrimônio positivos; indisponível para empresas com prejuízo.",
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
    "dividend_growth": {
        "label": "Crescimento dos proventos",
        "definition": "Ritmo anual de crescimento dos proventos por cota na janela de 5 anos "
        "(compara a média dos 2 últimos anos com a dos 2 primeiros). É o segundo motor da bola "
        "de neve: além de reinvestir, os próprios dividendos aumentam.",
        "source": "calculado: CAGR dos proventos por ano (StatusInvest)",
        "interpretation": "Positivo = dividendos crescendo. Negativo = encolhendo (cuidado: "
        "yield alto com proventos caindo costuma ser armadilha). O preset Dividend Growth "
        "exige crescimento positivo.",
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
    "sector_besst": {
        "label": "Setor perene (Barsi/BESST)",
        "definition": "Afinidade do setor do ativo com os setores essenciais que Luiz Barsi "
        "prioriza: Bancos, Energia, Saneamento, Seguros e Telecomunicações (BESST). São setores "
        "de demanda estável, que costumam sustentar dividendos no longo prazo.",
        "source": "calculado: setor (Fundamentus) cruzado com a lista BESST",
        "interpretation": "1 = setor perene clássico de dividendos. Não exclui outros setores, "
        "só dá preferência aos mais defensivos.",
    },
    "strategy": {
        "label": "Estratégia",
        "definition": "Preset inspirado em grandes investidores, com DOIS efeitos: muda os pesos "
        "das métricas E filtra o universo. 'Barsi' exige setor BESST + consistência alta + "
        "liquidez; 'Bazin' exige preço abaixo do teto; 'Graham' exige lucro positivo e "
        "P/L×P/VP ≤ 22,5; 'Dividend Growth' exige proventos crescendo. Quem não passa no filtro "
        "recebe score 0 com o motivo explicado.",
        "source": "configuração (presets + filtros de elegibilidade)",
        "interpretation": "Escolha conforme seu objetivo. Os pesos ficam visíveis na tela, e os "
        "excluídos mostram 'Não elegível' com a razão.",
    },
    "rebalance_gap": {
        "label": "Rebalanceamento",
        "definition": "O quanto este ativo/classe está abaixo do alvo que você definiu para a "
        "carteira. Comprar o que está sub-alocado aproxima a carteira da meta.",
        "source": "calculado: peso-alvo − peso-atual (carteira do Ghostfolio vs seus alvos)",
        "interpretation": "Quanto mais abaixo do alvo, maior a prioridade de aporte.",
    },
    "composite_score": {
        "label": "Score",
        "definition": "Nota final de 0 a 1 em três passos: (1) média ponderada das métricas das "
        "4 famílias — desconto, dividendos, rebalanceamento e setor perene; (2) MULTIPLICADA "
        "pelo fator de qualidade (selo 🟢/🟡/🔴 — prejuízo, dívida alta, payout insustentável e "
        "baixa liquidez derrubam a nota); (3) zerada se o ativo não passa no filtro da "
        "estratégia escolhida.",
        "source": "calculado: (Σ peso × valor normalizado) × fator de qualidade, com filtro de elegibilidade",
        "interpretation": "Use como ranking, não como verdade absoluta. A soma das contribuições "
        "do detalhamento dá a nota-base; o fator de qualidade explica a diferença até o score final.",
    },
    "quality_factor": {
        "label": "Fator de qualidade",
        "definition": "Multiplicador de 0 a 1 aplicado sobre a nota-base para afundar 'value "
        "traps' (barato que paga muito porque está afundando): prejuízo ×0,5, dívida alta, "
        "payout acima do sustentável e liquidez baixa reduzem o fator. Dado ausente é neutro.",
        "source": "calculado: penalidades sobre P/L, dívida/EBIT, payout e liquidez (Fundamentus)",
        "interpretation": "1,0 = nenhum alerta. Abaixo de ~0,6 o selo fica vermelho — leia as "
        "red flags antes de comprar.",
    },
    "weight": {
        "label": "Peso",
        "definition": "O quanto cada métrica influencia o score final. Você pode ajustar os "
        "pesos para priorizar desconto, dividendos ou rebalanceamento.",
        "source": "configuração (pesos default ou ajustados por você)",
        "interpretation": "A soma dos pesos é 1. Ex: 0,35 em valuation = 35% do score.",
    },
    "normalized": {
        "label": "Valor normalizado",
        "definition": "O valor cru convertido para a escala 0–1, por UMA de três regras: "
        "percentil entre pares do mesmo macro-setor/classe (P/VP, P/L, DY); âncora absoluta — "
        "distância a um valor justo conhecido (margens de Graham e de Bazin, crescimento); ou "
        "direto, quando o valor já é 0–1 (consistência, rebalanceamento, setor).",
        "source": "calculado: percentil entre pares, âncora absoluta ou valor direto, conforme a métrica",
        "interpretation": "Permite somar coisas de unidades diferentes de forma justa. Nas "
        "métricas com âncora, estar acima do teto vale 0 mesmo que todos os pares estejam piores.",
    },
    "weight_position": {
        "label": "Peso na carteira",
        "definition": "Quanto este ativo representa do valor total da sua carteira hoje.",
        "source": "Ghostfolio, valor da posição ÷ valor total",
        "interpretation": "Ajuda a ver concentração: pesos muito altos em um ativo aumentam o risco.",
    },
    "suggested_amount": {
        "label": "Valor sugerido",
        "definition": "Quanto do seu aporte de hoje o plano sugere colocar neste ativo, já "
        "arredondado para um número inteiro de cotas pelo preço atual.",
        "source": "calculado: divisão do aporte por classe e por score, ajustada por lote",
        "interpretation": "A sobra de arredondamento aparece em 'não alocado'.",
    },
    "data_completeness": {
        "label": "Completude dos dados",
        "definition": "Quantas das métricas previstas tinham dado disponível para este ativo. "
        "Quando falta dado, a métrica sai e o peso é redividido só DENTRO da mesma família — "
        "família inteira sem dado contribui zero, então pouca cobertura limita a nota máxima. "
        "Nunca inventamos número.",
        "source": "calculado: métricas disponíveis ÷ métricas previstas",
        "interpretation": "Ranking com completude baixa (ex: 2/9) tem nota naturalmente limitada "
        "e merece mais cautela.",
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
    "income_target": {
        "label": "Meta de renda mensal",
        "definition": "A renda passiva mensal (em reais DE HOJE) com que você quer viver de "
        "dividendos. O Aportador compara essa meta com a renda atual estimada da carteira e "
        "calcula quanto aportar por mês e em quantos anos você chega lá.",
        "source": "configuração (preferências: meta, horizonte, crescimento e inflação esperada)",
        "interpretation": "A comparação usa a renda LÍQUIDA (após IR do JCP) e desconta a "
        "inflação esperada — R$ 5.000 daqui a 20 anos valem menos que R$ 5.000 hoje.",
    },
    "fixed_income_yield": {
        "label": "Rendimento da reserva",
        "definition": "Taxa anualizada (base 252 dias úteis) derivada das suas atualizações de "
        "saldo, ponderando aportes e resgates pelo tempo em que o dinheiro ficou aplicado "
        "(método Modified Dietz). Comparada ao CDI do período (% do CDI).",
        "source": "calculado: lançamentos da conta (saldos, aportes, resgates) + CDI do Banco Central",
        "interpretation": "~100% do CDI é o esperado para uma boa reserva líquida. Muito abaixo, "
        "considere trocar de produto; o número fica mais preciso a cada atualização de saldo.",
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
