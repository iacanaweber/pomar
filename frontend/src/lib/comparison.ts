/** Carteira ATUAL × carteira PLANEJADA — aritmética pura, longe do React.
 *
 *  Os dois lados usam o MESMO denominador: o patrimônio de renda variável lido do
 *  Ghostfolio. É o que torna a comparação honesta — o peso atual de um ativo inclui no
 *  divisor até o que está fora da carteira alvo (o legado), que é justamente o que dilui
 *  os demais. A reserva/renda fixa fica de fora dos dois lados, como já acontece nas metas
 *  por classe.
 */
import { round2, shareOfTotal } from "./basket";
import { INVESTABLE_CLASSES } from "./classes";

/** Desvio abaixo do qual o ativo é considerado "no alvo" (p.p.). */
export const AT_TARGET_PP = 0.5;

export type RowStatus =
  | "ok" // dentro da tolerância
  | "below" // abaixo do alvo: destino dos próximos aportes
  | "above" // acima do alvo: não aportar aqui
  | "off_target" // tem posição, mas não está na carteira alvo (legado a diluir)
  | "not_bought"; // está na carteira alvo, mas ainda não comprado

export interface ComparisonRow {
  ticker: string;
  cls: string;
  currentPct: number; // % do patrimônio hoje
  targetPct: number; // % do patrimônio planejado
  deltaPp: number; // alvo − atual, em pontos percentuais (negativo = falta comprar)
  deltaBrl: number; // quanto falta comprar (positivo) ou sobra (negativo), em R$
  currentValue: number;
  status: RowStatus;
}

export interface ComparisonClassRow {
  cls: string;
  currentPct: number;
  targetPct: number;
  deltaPp: number;
  deltaBrl: number;
}

export interface Comparison {
  rows: ComparisonRow[];
  byClass: ComparisonClassRow[];
  totalValue: number;
  /** Soma das metas por classe (100 quando bem configurada). */
  targetSumPct: number;
  /** % do patrimônio que está em ativos fora da carteira alvo. */
  offTargetPct: number;
  hasTarget: boolean;
}

interface PositionLike {
  ticker: string;
  asset_class: string;
  value: number;
}

function classify(currentPct: number, targetPct: number): RowStatus {
  if (targetPct <= 0) return "off_target";
  if (currentPct <= 0) return "not_bought";
  const delta = targetPct - currentPct;
  if (Math.abs(delta) < AT_TARGET_PP) return "ok";
  return delta > 0 ? "below" : "above";
}

export function buildComparison(
  positions: PositionLike[],
  totalValue: number,
  targets: Record<string, number>,
  classTargets: Record<string, Record<string, number>>,
): Comparison {
  const total = totalValue > 0 ? totalValue : 0;

  // peso-alvo de cada ticker sobre a carteira INTEIRA (meta da classe × peso na cesta)
  const targetPctByTicker = new Map<string, { cls: string; pct: number }>();
  for (const cls of INVESTABLE_CLASSES) {
    const classPct = round2((targets[cls] ?? 0) * 100);
    for (const [ticker, weight] of Object.entries(classTargets[cls] ?? {})) {
      targetPctByTicker.set(ticker.toUpperCase(), {
        cls,
        pct: shareOfTotal(classPct, round2(weight * 100)),
      });
    }
  }

  const currentByTicker = new Map<string, PositionLike>();
  for (const p of positions) currentByTicker.set(p.ticker.toUpperCase(), p);

  const tickers = new Set([...targetPctByTicker.keys(), ...currentByTicker.keys()]);
  const rows: ComparisonRow[] = [];
  for (const ticker of tickers) {
    const target = targetPctByTicker.get(ticker);
    const position = currentByTicker.get(ticker);
    const currentValue = position?.value ?? 0;
    const currentPct = total > 0 ? round2((currentValue / total) * 100) : 0;
    const targetPct = target?.pct ?? 0;
    const deltaPp = round2(targetPct - currentPct);
    rows.push({
      ticker,
      cls: target?.cls ?? position?.asset_class ?? "UNKNOWN",
      currentPct,
      targetPct,
      deltaPp,
      deltaBrl: round2((deltaPp / 100) * total),
      currentValue,
      status: classify(currentPct, targetPct),
    });
  }
  // maior desvio primeiro: o topo da lista é o que precisa de decisão
  rows.sort((a, b) => Math.abs(b.deltaPp) - Math.abs(a.deltaPp) || a.ticker.localeCompare(b.ticker));

  const byClass: ComparisonClassRow[] = INVESTABLE_CLASSES.map((cls) => {
    const inClass = rows.filter((r) => r.cls === cls);
    const currentPct = round2(inClass.reduce((s, r) => s + r.currentPct, 0));
    const targetPct = round2((targets[cls] ?? 0) * 100);
    const deltaPp = round2(targetPct - currentPct);
    return { cls, currentPct, targetPct, deltaPp, deltaBrl: round2((deltaPp / 100) * total) };
  });

  return {
    rows,
    byClass,
    totalValue: total,
    targetSumPct: round2(
      INVESTABLE_CLASSES.reduce((s, c) => s + (targets[c] ?? 0) * 100, 0),
    ),
    offTargetPct: round2(
      rows.filter((r) => r.status === "off_target").reduce((s, r) => s + r.currentPct, 0),
    ),
    hasTarget: targetPctByTicker.size > 0,
  };
}
