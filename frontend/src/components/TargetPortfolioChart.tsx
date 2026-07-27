import { CLASS_LABEL, INVESTABLE_CLASSES } from "../lib/classes";
import { shareOfTotal, sumPct, type Row } from "../lib/basket";

/** Cores das CLASSES. Uma matiz por classe, em ordem fixa (nunca cicladas): a cor segue
 *  a entidade, não a posição na lista. Steps validados para as duas superfícies do app
 *  (--card #ffffff / #171c14) na lista de pares adjacentes — que é a que vale para barras
 *  empilhadas. Dentro de cada classe, os ativos são STEPS da mesma matiz (rampa
 *  sequencial: mais escuro = maior peso), então a identidade do ativo vem do rótulo, não
 *  da cor. Trocar um valor aqui exige rodar o validador de paleta de novo. */
const CLASS_HUE: Record<string, string> = {
  STOCK: "var(--viz-stock)",
  FII: "var(--viz-fii)",
  ETF: "var(--viz-etf)",
  BDR: "var(--viz-bdr)",
};

const fmt = (n: number) => `${n.toFixed(2).replace(".", ",")}%`;

/** Step da rampa sequencial: o maior peso fica na matiz cheia e os menores clareiam em
 *  direção à superfície do card. Monotônico com a magnitude, matiz constante. */
function step(hue: string, index: number, count: number): string {
  if (count <= 1) return hue;
  const mix = 100 - Math.round((index / (count - 1)) * 42); // 100% → 58%
  return `color-mix(in oklab, ${hue} ${mix}%, var(--card))`;
}

interface ClassRow {
  cls: string;
  classPct: number;
  rows: Row[];
}

/** Distribuição da carteira ALVO: quanto cada classe pesa no total e, dentro dela, quanto
 *  cada ativo representa DO TOTAL (meta da classe × peso na cesta).
 *
 *  Todas as barras dividem o mesmo trilho de 100% = a carteira inteira, então dá para
 *  comparar classes a olho: metade do trilho é metade da carteira. */
export function TargetPortfolioChart({ classes }: { classes: ClassRow[] }) {
  const totalMeta = classes.reduce((s, c) => s + c.classPct, 0);
  const configured = classes.filter((c) => c.classPct > 0 && c.rows.length > 0);

  return (
    <section className="card tp-chart">
      <div className="tp-chart-head">
        <h2>Distribuição da carteira alvo</h2>
        <span className={`muted tp-chart-sum ${Math.abs(totalMeta - 100) > 0.5 ? "warn" : ""}`}>
          metas somam {fmt(totalMeta)}
        </span>
      </div>

      {configured.length === 0 ? (
        <p className="muted">
          Defina as metas por classe e a composição de cada uma para ver a distribuição.
        </p>
      ) : (
        <ul className="tp-rows">
          {INVESTABLE_CLASSES.map((cls) => {
            const item = classes.find((c) => c.cls === cls);
            const classPct = item?.classPct ?? 0;
            // maior peso primeiro: a rampa de cor fica monotônica com a magnitude
            const rows = [...(item?.rows ?? [])].sort((a, b) => b.pct - a.pct);
            const basketSum = sumPct(rows);
            const hue = CLASS_HUE[cls];
            const motivo =
              classPct <= 0 ? "meta 0%" : rows.length === 0 ? "sem composição" : null;

            return (
              <li className={`tp-row ${motivo ? "tp-row-off" : ""}`} key={cls}>
                <div className="tp-row-head">
                  <span className="tp-class">{CLASS_LABEL[cls]}</span>
                  <span className="tp-class-pct">
                    {motivo ? <span className="muted">{motivo}</span> : `${fmt(classPct)} do total`}
                  </span>
                </div>

                <div
                  className="tp-track"
                  role="img"
                  aria-label={
                    motivo
                      ? `${CLASS_LABEL[cls]}: ${motivo}`
                      : `${CLASS_LABEL[cls]}: ${fmt(classPct)} da carteira, em ${rows.length} ativos`
                  }
                >
                  <div className="tp-fill" style={{ width: `${Math.min(100, classPct)}%` }}>
                    {rows.map((r, i) => (
                      <span
                        key={r.ticker}
                        className="tp-seg"
                        style={{ flexGrow: Math.max(r.pct, 0.01), background: step(hue, i, rows.length) }}
                        title={`${r.ticker}: ${fmt(shareOfTotal(classPct, r.pct))} do total (${fmt(r.pct)} de ${CLASS_LABEL[cls]})`}
                      />
                    ))}
                  </div>
                </div>

                {rows.length > 0 && (
                  <ul className="tp-legend">
                    {rows.map((r, i) => (
                      <li key={r.ticker}>
                        <span
                          className="tp-dot"
                          style={{ background: step(hue, i, rows.length) }}
                          aria-hidden="true"
                        />
                        <span className="tp-legend-ticker">{r.ticker}</span>
                        <span className="tp-legend-pct">{fmt(shareOfTotal(classPct, r.pct))}</span>
                      </li>
                    ))}
                  </ul>
                )}
                {rows.length > 0 && Math.abs(basketSum - 100) > 0.1 && (
                  <span className="tp-row-warn">
                    composição soma {fmt(basketSum)} — as fatias acima estão proporcionais, mas
                    o valor real só fecha em 100%
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      )}
      <p className="muted tp-note">
        A % de cada ativo é sobre a carteira INTEIRA: meta da classe × peso dele na classe.
      </p>
    </section>
  );
}
