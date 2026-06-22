// Formatação — fonte ÚNICA (substitui as cópias de `brl` espalhadas em 3 componentes).

export function money(value: number, currency = "BRL"): string {
  return value.toLocaleString("pt-BR", { style: "currency", currency });
}

export function pct(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`;
}

/** Converte texto pt-BR ("1.234,56") em número. Remove separador de milhar e usa
 *  a vírgula como decimal — corrige o bug do parseFloat ingênuo ("1.000,50" -> 1). */
export function parseBRL(input: string): number {
  const cleaned = input.trim().replace(/\./g, "").replace(",", ".");
  const n = parseFloat(cleaned);
  return Number.isFinite(n) ? n : NaN;
}

/** Data ISO -> "HH:MM de DD/MM" (para carimbo de frescor). */
export function shortDateTime(iso?: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "2-digit",
  });
}
