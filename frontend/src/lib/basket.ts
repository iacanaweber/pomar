/** Aritmética da carteira alvo — pura e testável, longe do React.
 *
 *  Todos os pesos aqui são PERCENTUAIS (0..100) com 2 casas decimais, porque é assim que
 *  o usuário digita ("21,23%"). A conversão para fração (0..1) acontece só na borda, na
 *  hora de salvar nas preferências.
 */

export interface Row {
  ticker: string;
  pct: number;
}

/** Tolerância da soma, em pontos percentuais — a mesma do validador do backend. */
export const SUM_TOLERANCE = 0.1;

/** Arredonda para 2 casas sem o ruído de ponto flutuante (0.1+0.2 e afins). */
export const round2 = (n: number): number => Math.round((n + Number.EPSILON) * 100) / 100;

export const sumPct = (rows: Row[]): number => round2(rows.reduce((s, r) => s + (r.pct || 0), 0));

export const sumOk = (rows: Row[]): boolean => Math.abs(sumPct(rows) - 100) <= SUM_TOLERANCE;

/** Estado da soma para a UI: acima de 100, abaixo, ou fechada. */
export type SumState = "over" | "under" | "ok";

export function sumState(rows: Row[]): SumState {
  if (rows.length === 0) return "ok";
  const total = sumPct(rows);
  if (total > 100 + SUM_TOLERANCE) return "over";
  if (total < 100 - SUM_TOLERANCE) return "under";
  return "ok";
}

/** Distribui o resíduo do arredondamento no MAIOR peso, para a soma fechar 100,00 exatos.
 *  Sem isso, 3 ativos a 33,33% somam 99,99% e o salvamento fica bloqueado para sempre. */
function absorbDrift(rows: Row[]): Row[] {
  if (!rows.length) return rows;
  const drift = round2(100 - sumPct(rows));
  if (drift === 0) return rows;
  let biggest = 0;
  rows.forEach((r, i) => {
    if (r.pct > rows[biggest].pct) biggest = i;
  });
  const out = rows.map((r) => ({ ...r }));
  out[biggest].pct = round2(Math.max(0, out[biggest].pct + drift));
  return out;
}

/** Ajusta a composição para fechar 100% PRESERVANDO as proporções relativas (×100/soma).
 *
 *  Serve nos dois sentidos (soma acima ou abaixo de 100) e nunca zera nem torna negativo
 *  um peso pequeno — ao contrário de subtrair a mesma quantidade de todos. Soma zero não
 *  tem proporção a preservar: cai na divisão igualitária.
 */
export function scaleTo100(rows: Row[]): Row[] {
  if (!rows.length) return rows;
  const total = sumPct(rows);
  if (total <= 0) return distributeEvenly(rows);
  const factor = 100 / total;
  return absorbDrift(rows.map((r) => ({ ...r, pct: round2((r.pct || 0) * factor) })));
}

/** Mesmo peso para todos, com o resíduo no primeiro (que passa a ser o maior). */
export function distributeEvenly(rows: Row[]): Row[] {
  if (!rows.length) return rows;
  const even = round2(100 / rows.length);
  return absorbDrift(rows.map((r) => ({ ...r, pct: even })));
}

/** Composição a partir dos pesos ATUAIS da carteira (valor de cada posição da classe). */
export function fromCurrentValues(positions: { ticker: string; value: number }[]): Row[] {
  const total = positions.reduce((s, p) => s + p.value, 0);
  if (!positions.length || total <= 0) return [];
  const rows = positions
    .map((p) => ({ ticker: p.ticker, pct: round2((p.value / total) * 100) }))
    .sort((a, b) => b.pct - a.pct);
  return absorbDrift(rows);
}

/** Fatia do ativo sobre a carteira INTEIRA: meta da classe × peso dele na cesta.
 *
 *  É a conta que responde "20% das minhas ações, e ações são 50% do total, então esta
 *  ação é 10% do total". Ambos os argumentos em percentual; devolve percentual.
 */
export const shareOfTotal = (classPct: number, rowPct: number): number =>
  round2((classPct * rowPct) / 100);
