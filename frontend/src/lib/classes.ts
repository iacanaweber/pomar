/** Classes de renda variável que recebem aporte (a reserva/renda fixa é tratada à parte).
 *  A ordem é a que aparece na UI — do que pesa mais na carteira típica para o que pesa menos. */
export const INVESTABLE_CLASSES = ["STOCK", "FII", "ETF", "BDR"] as const;

export type InvestableClass = (typeof INVESTABLE_CLASSES)[number];

export const CLASS_LABEL: Record<string, string> = {
  STOCK: "Ações",
  FII: "FIIs",
  ETF: "ETFs",
  BDR: "BDRs",
};

export const classLabel = (cls: string): string => CLASS_LABEL[cls] ?? cls;
