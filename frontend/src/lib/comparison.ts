/** Carteira ATUAL × carteira PLANEJADA — aritmética pura, longe do React.
 *
 *  Cada posição tem um ESTADO derivado (nunca armazenado):
 *
 *  * `IN_TARGET` — está na cesta alvo com peso > 0.
 *  * `LEGACY`  — a posição existe, mas o peso alvo é zero ou o ativo não está em cesta
 *                nenhuma. É o caso real de quem mudou de estratégia e ainda não vendeu.
 *  * `NEW`     — está no alvo e ainda não foi comprado.
 *
 *  **`LEGACY` não tem razão ao alvo.** Com alvo zero, "desvio percentual" e "quanto falta"
 *  não são números pequenos: não existem. Por isso `targetPct`, `deltaPp` e `deltaBrl` são
 *  `null` nessas linhas — o tipo é que impede a tela de inventar uma barra de progresso
 *  contra um denominador zero. O que essas posições têm é valor em R$ e participação no
 *  patrimônio, e é só isso que a tela mostra.
 *
 *  **Duas escalas, de propósito, e cada uma responde uma pergunta diferente.**
 *
 *  Por ATIVO (`rows`), o denominador exclui o legado: "dentro do capital que segue a
 *  estratégia, este ticker está no peso?". Diluir os pesos pelo que está de saída
 *  responderia outra coisa. O legado sai das linhas e aparece somado à parte.
 *
 *  Por CLASSE (`byClass`), o denominador é o PATRIMÔNIO INTEIRO, legado incluído: ali a
 *  pergunta é descritiva — "como minha carteira está composta hoje, e como eu queria que
 *  estivesse?". Foi assim que uma classe inteira em legado (ações de uma estratégia
 *  anterior) sumia da tela: `byClass` somava só `rows`, então a classe vinha com valor
 *  zero, indistinguível de uma que nunca existiu. Pior: como o denominador também excluía
 *  o legado, as classes restantes INFLAVAM até somar 100% e preenchiam o trilho —
 *  o buraco não ficava visível, e os ETFs pareciam mais perto do alvo do que estavam.
 *
 *  **Os alvos em R$ usam outra base**, escolhida por `legacyInTotal` (default `true`): o
 *  legado entra no patrimônio que serve de base para os alvos das demais classes. Isso
 *  aumenta o que falta comprar e mantém a carteira subalocada até a venda, que é o retrato
 *  honesto. Com `false`, os alvos são calculados só sobre o capital alinhado. As duas
 *  leituras convivem de propósito: a de p.p. compara FORMA, a de R$ compara TAMANHO — e
 *  quando elas discordam, a diferença é exatamente o dinheiro que está fora da estratégia.
 */
import { round2, shareOfTotal } from "./basket";
import { ALLOCATION_CLASSES, INVESTABLE_CLASSES, RENDA_FIXA } from "./classes";

/** Desvio abaixo do qual o ativo é considerado "no alvo" (p.p.). */
export const AT_TARGET_PP = 0.5;

/** Estado da posição em relação à carteira alvo. */
export type PositionState = "IN_TARGET" | "LEGACY" | "NEW";

/** Direção do desvio — só existe para quem TEM alvo. */
export type TargetStatus = "ok" | "below" | "above";

export interface ComparisonRow {
  ticker: string;
  cls: string;
  state: PositionState;
  currentValue: number;
  /** % do capital ALINHADO (o legado fica fora do denominador). */
  currentPct: number;
  /** % do PATRIMÔNIO — a leitura que faz sentido para o legado. */
  portfolioPct: number;
  /** `null` em LEGACY: não há alvo contra o qual medir. */
  targetPct: number | null;
  targetBrl: number | null;
  deltaPp: number | null;
  deltaBrl: number | null;
  status: TargetStatus | null;
}

export interface ComparisonClassRow {
  cls: string;
  /** Valor da classe INTEIRA, legado incluído. */
  currentValue: number;
  /** % do PATRIMÔNIO — diferente de `ComparisonRow.currentPct`, que é % do alinhado. */
  currentPct: number;
  targetPct: number;
  deltaPp: number;
  deltaBrl: number;
}

export interface Comparison {
  /** Linhas com alvo: `IN_TARGET` e `NEW`. O legado sai daqui e vive em `legacy`. */
  rows: ComparisonRow[];
  legacy: ComparisonRow[];
  byClass: ComparisonClassRow[];
  /** Patrimônio: renda variável + renda fixa que conta na carteira. */
  totalValue: number;
  /** Capital que segue a estratégia (patrimônio − legado). */
  alignedValue: number;
  legacyValue: number;
  /** Fatia do PATRIMÔNIO que está fora do alvo (0..100). */
  legacyPct: number;
  /** Base sobre a qual os alvos em R$ foram calculados. */
  targetBase: number;
  legacyInTotal: boolean;
  /** Soma das metas por classe (100 quando bem configurada). */
  targetSumPct: number;
  hasTarget: boolean;
}

interface PositionLike {
  ticker: string;
  asset_class: string;
  value: number;
}

interface Options {
  /** Saldo das contas de renda fixa que contam na carteira (sem as posições de RV). */
  rendaFixaValue?: number;
  legacyInTotal?: boolean;
}

/** Divisão que devolve 0 quando não há denominador — nunca `Infinity` nem `NaN`. */
const share = (value: number, total: number): number =>
  total > 0 ? round2((value / total) * 100) : 0;

function statusOf(deltaPp: number): TargetStatus {
  if (Math.abs(deltaPp) < AT_TARGET_PP) return "ok";
  return deltaPp > 0 ? "below" : "above";
}

export function buildComparison(
  positions: PositionLike[],
  totalValue: number,
  targets: Record<string, number>,
  classTargets: Record<string, Record<string, number>>,
  options: Options = {},
): Comparison {
  const rendaFixaAccounts = Math.max(0, options.rendaFixaValue ?? 0);
  const legacyInTotal = options.legacyInTotal ?? true;
  const rvTotal = totalValue > 0 ? totalValue : 0;

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

  // Posições atribuídas à cesta de renda fixa não são tickers da comparação: os itens
  // daquela cesta são indexadores. Elas somam no valor da classe, junto com as contas.
  const rvPositions = positions.filter((p) => p.asset_class !== RENDA_FIXA);
  const rendaFixaValue =
    rendaFixaAccounts +
    positions.filter((p) => p.asset_class === RENDA_FIXA).reduce((s, p) => s + p.value, 0);

  const currentByTicker = new Map<string, PositionLike>();
  for (const p of rvPositions) currentByTicker.set(p.ticker.toUpperCase(), p);

  const patrimonio = round2(rvTotal + rendaFixaAccounts);
  const legacyValue = round2(
    [...currentByTicker.values()]
      .filter((p) => (targetPctByTicker.get(p.ticker.toUpperCase())?.pct ?? 0) <= 0)
      .reduce((s, p) => s + p.value, 0),
  );
  const alignedValue = round2(Math.max(0, patrimonio - legacyValue));
  const targetBase = legacyInTotal ? patrimonio : alignedValue;

  const rows: ComparisonRow[] = [];
  const legacy: ComparisonRow[] = [];
  const tickers = new Set([...targetPctByTicker.keys(), ...currentByTicker.keys()]);
  for (const ticker of tickers) {
    const target = targetPctByTicker.get(ticker);
    const position = currentByTicker.get(ticker);
    const currentValue = position?.value ?? 0;
    const targetPct = target?.pct ?? 0;
    const base = {
      ticker,
      cls: target?.cls ?? position?.asset_class ?? "UNKNOWN",
      currentValue,
      currentPct: share(currentValue, alignedValue),
      portfolioPct: share(currentValue, patrimonio),
    };

    if (targetPct <= 0) {
      // Sem alvo não há razão ao alvo: os campos de desvio ficam nulos de propósito.
      legacy.push({
        ...base,
        currentPct: 0, // o legado não participa do denominador alinhado
        state: "LEGACY",
        targetPct: null,
        targetBrl: null,
        deltaPp: null,
        deltaBrl: null,
        status: null,
      });
      continue;
    }

    const targetBrl = round2((targetPct / 100) * targetBase);
    const deltaPp = round2(targetPct - base.currentPct);
    rows.push({
      ...base,
      state: currentValue > 0 ? "IN_TARGET" : "NEW",
      targetPct,
      targetBrl,
      deltaPp,
      deltaBrl: round2(targetBrl - currentValue),
      status: statusOf(deltaPp),
    });
  }

  // maior desvio primeiro: o topo da lista é o que precisa de decisão
  rows.sort(
    (a, b) =>
      Math.abs(b.deltaPp ?? 0) - Math.abs(a.deltaPp ?? 0) || a.ticker.localeCompare(b.ticker),
  );
  legacy.sort((a, b) => b.currentValue - a.currentValue || a.ticker.localeCompare(b.ticker));

  // `[...rows, ...legacy]`, e não só `rows`: a leitura por classe é DESCRITIVA e tem de
  // mostrar a carteira inteira. Uma classe cujas posições são todas legado precisa
  // aparecer com o valor que ela realmente tem. `RENDA_FIXA` sempre foi correta aqui —
  // `rendaFixaValue` já era o total da classe — e era a única.
  const todasAsLinhas = [...rows, ...legacy];
  const byClass: ComparisonClassRow[] = ALLOCATION_CLASSES.map((cls) => {
    const currentValue =
      cls === RENDA_FIXA
        ? rendaFixaValue
        : round2(
            todasAsLinhas.filter((r) => r.cls === cls).reduce((s, r) => s + r.currentValue, 0),
          );
    // Patrimônio, não capital alinhado: é o que faz Σ currentPct fechar 100% e o que faz
    // as colunas Hoje / Alvo / Desvio da tabela subtraírem de fato.
    const currentPct = share(currentValue, patrimonio);
    const targetPct = round2((targets[cls] ?? 0) * 100);
    const deltaPp = round2(targetPct - currentPct);
    return {
      cls,
      currentValue,
      currentPct,
      targetPct,
      deltaPp,
      deltaBrl: round2((targetPct / 100) * targetBase - currentValue),
    };
  });

  const rfTargetPct = round2((targets[RENDA_FIXA] ?? 0) * 100);
  return {
    rows,
    legacy,
    byClass,
    totalValue: patrimonio,
    alignedValue,
    legacyValue,
    legacyPct: share(legacyValue, patrimonio),
    targetBase,
    legacyInTotal,
    targetSumPct: round2(ALLOCATION_CLASSES.reduce((s, c) => s + (targets[c] ?? 0) * 100, 0)),
    hasTarget: targetPctByTicker.size > 0 || rfTargetPct > 0,
  };
}
