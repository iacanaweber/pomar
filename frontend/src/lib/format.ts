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

/** Hoje no formato ISO local "yyyy-mm-dd" (sem fuso/UTC surpresa). */
export function todayISO(): string {
  const d = new Date();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}

/** "yyyy-mm-dd" -> "dd/mm/yyyy". */
export function isoToBR(iso: string): string {
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})/);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : iso;
}

/** Hoje no formato brasileiro "dd/mm/yyyy". */
export function todayBR(): string {
  return isoToBR(todayISO());
}

/** "dd/mm/yyyy" -> "yyyy-mm-dd" (ou null se inválido). Aceita 1-2 dígitos em dia/mês. */
export function brToISO(input: string): string | null {
  const m = input.trim().match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (!m) return null;
  const dd = m[1].padStart(2, "0");
  const mm = m[2].padStart(2, "0");
  const iso = `${m[3]}-${mm}-${dd}`;
  const d = new Date(`${iso}T00:00:00`);
  // valida o calendário (ex.: 31/02 não existe)
  return Number.isNaN(d.getTime()) || d.getDate() !== Number(dd) ? null : iso;
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
