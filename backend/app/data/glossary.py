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
        "definition": "Quanto o ativo pagou em dividendos nos últimos 12 meses dividido pelo "
        "preço atual. É a 'renda' que o ativo gera por reais investidos.",
        "source": "calculado: último ano de proventos (StatusInvest) ÷ preço",
        "interpretation": "Maior é melhor para renda, mas yields muito altos podem ser "
        "pontuais (não se repetem) — por isso penalizamos os que parecem não recorrentes.",
    },
    "graham": {
        "label": "Margem Graham",
        "definition": "Critério de valor de Benjamin Graham: uma ação 'barata' tende a ter "
        "P/L e P/VP baixos. A regra clássica diz que o produto P/L × P/VP deve ficar até 22,5 "
        "(equivale a P/L 15 e P/VP 1,5). Quanto menor o produto, maior a margem de segurança.",
        "source": "calculado: P/L × P/VP (brapi) comparado ao teto 22,5 de Graham",
        "interpretation": "Produto bem abaixo de 22,5 sugere preço com desconto e margem de "
        "segurança. Aplica-se a ações, não a FIIs.",
    },
    "bazin_ceiling": {
        "label": "Margem Bazin (preço-teto)",
        "definition": "Método de Décio Bazin: o 'preço-teto' justo é o dividendo médio anual "
        "dividido por 6% (DY-alvo). Comprar abaixo desse teto garante um yield mínimo de 6%. "
        "A margem mostra o quanto o preço atual está abaixo (positivo) ou acima do teto.",
        "source": "calculado: preço-teto = dividendo médio ÷ 0,06; margem = (teto − preço) ÷ teto",
        "interpretation": "Margem positiva = comprando abaixo do teto (bom). Negativa = caro "
        "frente ao histórico de proventos.",
    },
    "dividend_consistency": {
        "label": "Consistência de dividendos",
        "definition": "Há quantos dos últimos anos o ativo pagou dividendos de forma recorrente. "
        "Recompensa pagadoras regulares (estilo Barsi/Bazin) e desconfia de proventos pontuais.",
        "source": "calculado: anos com pagamento ÷ anos analisados (histórico brapi)",
        "interpretation": "Perto de 1 = paga quase todo ano. Baixo = renda irregular, menos "
        "confiável para viver de dividendos.",
    },
    "sector_besst": {
        "label": "Setor perene (Barsi/BESST)",
        "definition": "Afinidade do setor do ativo com os setores essenciais que Luiz Barsi "
        "prioriza: Bancos, Energia, Saneamento, Seguros e Telecomunicações (BESST). São setores "
        "de demanda estável, que costumam sustentar dividendos no longo prazo.",
        "source": "calculado: setor (Ghostfolio/brapi) cruzado com a lista BESST",
        "interpretation": "1 = setor perene clássico de dividendos. Não exclui outros setores, "
        "só dá preferência aos mais defensivos.",
    },
    "strategy": {
        "label": "Estratégia",
        "definition": "Conjunto de pesos pré-definidos inspirados em grandes investidores. "
        "'Barsi' favorece dividendos e setores perenes; 'Bazin' o preço-teto; 'Graham' o "
        "desconto/valor; 'Equilibrado' mistura tudo. Mudar a estratégia só muda os pesos.",
        "source": "configuração (presets em config.py)",
        "interpretation": "Escolha conforme seu objetivo. Os pesos resultantes ficam sempre "
        "visíveis na tela.",
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
        "definition": "Nota final de 0 a 1 que combina desconto (valuation), dividendos e "
        "necessidade de rebalanceamento, cada um com um peso. É a média ponderada das métricas.",
        "source": "calculado: soma de (peso × valor normalizado) de cada métrica",
        "interpretation": "Use como ranking, não como verdade absoluta. Abra a decomposição "
        "para ver de onde veio a nota.",
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
        "definition": "O valor cru convertido para uma escala de 0 a 1 comparando o ativo com "
        "seus pares do mesmo tipo/setor (percentil). 1 = melhor do grupo naquele critério.",
        "source": "calculado: percentil dentro do grupo de pares",
        "interpretation": "Permite somar coisas de unidades diferentes (P/VP, %, etc.) de forma justa.",
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
        "Quando falta dado, removemos a métrica e redistribuímos o peso — nunca inventamos número.",
        "source": "calculado: métricas disponíveis ÷ métricas previstas",
        "interpretation": "Ranking com completude baixa (ex: 2/4) merece mais cautela.",
    },
}


def get_glossary() -> Dict[str, Dict[str, str]]:
    return GLOSSARY
