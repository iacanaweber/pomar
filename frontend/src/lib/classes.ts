/** Classes cuja compra o app resolve em COTAS: têm cotação, lote e ticker.
 *  A ordem é a que aparece na UI — do que pesa mais na carteira típica para o que pesa menos. */
export const INVESTABLE_CLASSES = ["STOCK", "FII", "ETF", "BDR"] as const;

/** A carteira alvo inteira. RENDA_FIXA tem peso e déficit como qualquer classe, mas os
 *  itens da cesta dela são TAGS DE INDEXADOR e a compra é manual, feita fora do app — por
 *  isso ela não entra em INVESTABLE_CLASSES nem na comparação atual × alvo por ticker. */
export const RENDA_FIXA = "RENDA_FIXA";
export const ALLOCATION_CLASSES = [...INVESTABLE_CLASSES, RENDA_FIXA] as const;

export type InvestableClass = (typeof INVESTABLE_CLASSES)[number];

export const CLASS_LABEL: Record<string, string> = {
  STOCK: "Ações",
  FII: "FIIs",
  ETF: "ETFs",
  BDR: "BDRs",
  RENDA_FIXA: "Renda fixa",
};

export const classLabel = (cls: string): string => CLASS_LABEL[cls] ?? cls;

/** Ordena por PESO DECRESCENTE, com desempate ESTÁVEL pela ordem de entrada.
 *
 *  A ordem canônica (ALLOCATION_CLASSES) continua sendo a verdade de tudo que o usuário
 *  EDITA — campo que muda de lugar enquanto se digita é campo que se perde. Esta ordem é
 *  só de LEITURA: gráfico, legenda e lista de desvio, onde "o que pesa mais vem antes" é
 *  a única ordem que responde à pergunta da tela.
 *
 *  `weightOf` devolve o peso — meta %, valor em R$ ou |desvio|, tanto faz: a função só
 *  compara. Empate (inclusive todos os zeros) cai na ordem de entrada, então a lista
 *  NUNCA embaralha sozinha entre renders com os mesmos dados. Não muta a entrada.
 */
export function byWeightDesc<T>(items: readonly T[], weightOf: (item: T) => number): T[] {
  return items
    .map((item, i) => ({ item, i }))
    .sort((a, b) => (weightOf(b.item) || 0) - (weightOf(a.item) || 0) || a.i - b.i)
    .map(({ item }) => item);
}
