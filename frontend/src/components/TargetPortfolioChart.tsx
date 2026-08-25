import { CLASS_LABEL } from "../lib/classes";
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
  RENDA_FIXA: "var(--viz-rf)",
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

interface Segment {
  cls: string;
  ticker: string;
  sharePct: number;
  color: string;
  firstOfClass: boolean;
}

interface ClassView {
  cls: string;
  classPct: number;
  rows: Row[];
  basketSum: number;
  colors: string[];
  motivo: string | null;
}

/** Distribuição da carteira ALVO numa barra só: os 100% da carteira em uma linha, cada
 *  ativo ocupando a fatia que ele representa DO TOTAL (meta da classe × peso na cesta).
 *
 *  As classes não têm rótulo na barra — elas se distinguem pela matiz (todos os ativos de
 *  uma classe são steps da mesma cor) e por um respiro maior na virada. Os nomes vivem na
 *  legenda, que também é a "table view": todo valor é legível sem depender de hover.
 */
export function TargetPortfolioChart({ classes }: { classes: ClassRow[] }) {
  const totalMeta = classes.reduce((s, c) => s + c.classPct, 0);

  // Itera o prop `classes`, que já chega na ordem de leitura decidida pela página, em vez
  // de re-derivar da ordem canônica: a decisão de ordem mora num lugar só.
  const views: ClassView[] = classes.map(({ cls }) => {
    const item = classes.find((c) => c.cls === cls);
    const classPct = item?.classPct ?? 0;
    // maior peso primeiro: a rampa de cor fica monotônica com a magnitude
    const rows = [...(item?.rows ?? [])].sort((a, b) => b.pct - a.pct);
    return {
      cls,
      classPct,
      rows,
      basketSum: sumPct(rows),
      colors: rows.map((_, i) => step(CLASS_HUE[cls], i, rows.length)),
      motivo: classPct <= 0 ? "meta 0%" : rows.length === 0 ? "sem composição" : null,
    };
  });

  const segments: Segment[] = views.flatMap((v) =>
    v.motivo
      ? []
      : v.rows.map((r, i) => ({
          cls: v.cls,
          ticker: r.ticker,
          sharePct: shareOfTotal(v.classPct, r.pct),
          color: v.colors[i],
          firstOfClass: i === 0,
        })),
  );

  const allocated = segments.reduce((s, x) => s + x.sharePct, 0);
  // o que sobra do trilho é informação: essa fatia da carteira não está alocada
  const unallocated = Math.max(0, 100 - allocated);

  return (
    <section className="card tp-chart">
      <div className="tp-chart-head">
        <h2>Distribuição da carteira alvo</h2>
        <span className={`muted tp-chart-sum ${Math.abs(totalMeta - 100) > 0.5 ? "warn" : ""}`}>
          metas somam {fmt(totalMeta)}
        </span>
      </div>

      {segments.length === 0 ? (
        <p className="muted">
          Defina as metas por classe e a composição de cada uma.
        </p>
      ) : (
        <>
          <div
            className="tp-track"
            role="img"
            aria-label={`Carteira alvo: ${views
              .filter((v) => !v.motivo)
              .map((v) => `${CLASS_LABEL[v.cls]} ${fmt(v.classPct)}`)
              .join(", ")}${unallocated > 0.05 ? `, ${fmt(unallocated)} sem alocação` : ""}`}
          >
            <div className="tp-bar">
              {segments.map((s) => (
                <span
                  key={`${s.cls}-${s.ticker}`}
                  className={`tp-seg ${s.firstOfClass ? "tp-seg-class" : ""}`}
                  style={{ flexGrow: Math.max(s.sharePct, 0.01), background: s.color }}
                  title={`${s.ticker} · ${CLASS_LABEL[s.cls]}: ${fmt(s.sharePct)} do total`}
                />
              ))}
              {unallocated > 0.05 && (
                <span className="tp-seg tp-seg-empty" style={{ flexGrow: unallocated }} />
              )}
            </div>
          </div>

          <ul className="tp-classes">
            {views.map((v) => (
              <li className={`tp-class-item ${v.motivo ? "tp-class-off" : ""}`} key={v.cls}>
                <div className="tp-class-head">
                  <span className="tp-dot" style={{ background: CLASS_HUE[v.cls] }} aria-hidden="true" />
                  <span className="tp-class-name">{CLASS_LABEL[v.cls]}</span>
                  <span className="tp-class-pct">
                    {v.motivo ? <span className="muted">{v.motivo}</span> : `${fmt(v.classPct)} do total`}
                  </span>
                </div>
                {v.rows.length > 0 && (
                  <ul className="tp-legend">
                    {v.rows.map((r, i) => (
                      <li key={r.ticker}>
                        <span className="tp-dot" style={{ background: v.colors[i] }} aria-hidden="true" />
                        <span className="tp-legend-ticker">{r.ticker}</span>
                        <span className="tp-legend-pct">{fmt(shareOfTotal(v.classPct, r.pct))}</span>
                      </li>
                    ))}
                  </ul>
                )}
                {v.rows.length > 0 && Math.abs(v.basketSum - 100) > 0.1 && (
                  <span className="tp-class-warn">
                    composição soma {fmt(v.basketSum)}: as fatias são proporcionais, mas o
                    valor real só fecha em 100%
                  </span>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
      <p className="muted tp-note">
        % sobre a carteira inteira: meta da classe × peso na classe.
      </p>
    </section>
  );
}
