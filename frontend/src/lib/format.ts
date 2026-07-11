// Formatação — fonte ÚNICA (substitui as cópias de `brl` espalhadas em 3 componentes).

export function money(value: number, currency = "BRL"): string {
  return value.toLocaleString("pt-BR", { style: "currency", currency });
}

export function pct(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`;
}

/** Converte texto de dinheiro em número, aceitando pt-BR ("1.234,56") e o ponto
 *  decimal ("1500.00"). Regra: com vírgula, pontos são milhar; só com ponto, um único
 *  ponto seguido de 1-2 dígitos no fim é DECIMAL — antes, "1500.00" virava 150.000 e
 *  um aporte digitado assim gerava plano para cem vezes o valor. */
export function parseBRL(input: string): number {
  const s = input.trim();
  if (!s) return NaN;
  let cleaned: string;
  if (s.includes(",")) {
    cleaned = s.replace(/\./g, "").replace(",", ".");
  } else if (/^\d+\.\d{1,2}$/.test(s)) {
    cleaned = s; // "1500.00" / "99.9": ponto decimal
  } else {
    cleaned = s.replace(/\./g, ""); // "1.500" / "1.234.567": separador de milhar
  }
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
