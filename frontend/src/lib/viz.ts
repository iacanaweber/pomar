// Cor de gráfico — fonte ÚNICA.
//
// Antes existiam dois sistemas rivais. `CLASS_HUE` estava copiado em
// TargetPortfolioChart e PortfolioVsTarget (e já tinha divergido: uma cópia ganhou uma
// chave UNKNOWN que a outra não tem), e `lib/palette.ts` trazia 16 hex CRUS ciclados por
// índice, cegos ao modo escuro, usados só na rosca da Carteira. Resultado: a mesma classe
// de ativo aparecia em dois sistemas de cor dependendo da sub-aba aberta.

/** Uma matiz por CLASSE, em ordem fixa — nunca cicladas: a cor segue a entidade, não a
 *  posição na lista. Os valores moram no CSS (`--viz-*`), validados por contraste e
 *  ΔE nas duas superfícies de card. Trocar um deles exige revalidar o conjunto. */
export const CLASS_HUE: Record<string, string> = {
  STOCK: "var(--viz-stock)",
  FII: "var(--viz-fii)",
  ETF: "var(--viz-etf)",
  BDR: "var(--viz-bdr)",
  RENDA_FIXA: "var(--viz-rf)",
};

/** Classe sem matiz própria (inclusive "UNKNOWN") cai no cinza do tema. */
export function classHue(cls: string): string {
  return CLASS_HUE[cls] ?? "var(--muted)";
}

/** Ordem canônica das classes em qualquer gráfico. Fora dela, alfabética. */
export const CLASS_ORDER = ["ETF", "STOCK", "FII", "BDR", "RENDA_FIXA"];

export function byClassOrder(a: string, b: string): number {
  const ia = CLASS_ORDER.indexOf(a);
  const ib = CLASS_ORDER.indexOf(b);
  if (ia === -1 && ib === -1) return a.localeCompare(b);
  if (ia === -1) return 1;
  if (ib === -1) return -1;
  return ia - ib;
}

/** Step da rampa sequencial dentro de uma classe: o maior peso fica na matiz cheia e os
 *  menores clareiam em direção à superfície do card. Monotônico com a magnitude, matiz
 *  constante — a identidade do ativo vem do rótulo, não da cor.
 *
 *  `color-mix` com `var(--card)` é o que faz a rampa acompanhar o tema sozinha. */
export function step(hue: string, index: number, count: number): string {
  if (count <= 1) return hue;
  const mix = 100 - Math.round((index / (count - 1)) * 42); // 100% → 58%
  return `color-mix(in oklab, ${hue} ${mix}%, var(--card))`;
}

/** Cor para lista categórica de tamanho ARBITRÁRIO (rosca por ativo, por setor, por
 *  geografia) — onde não há classe para seguir.
 *
 *  Deriva das mesmas cinco matizes validadas em vez de uma rampa de hex à parte: ao dar a
 *  volta, cada ciclo clareia em direção ao card. Duas consequências boas: nada de hex cru
 *  cego ao tema, e as matizes que o usuário já associa a classes seguem sendo as
 *  primeiras que ele vê. */
export function categoricalHue(index: number): string {
  const matizes = CLASS_ORDER.map((c) => CLASS_HUE[c]);
  const base = matizes[index % matizes.length];
  const volta = Math.floor(index / matizes.length);
  if (volta === 0) return base;
  const mix = Math.max(40, 100 - volta * 22);
  return `color-mix(in oklab, ${base} ${mix}%, var(--card))`;
}
