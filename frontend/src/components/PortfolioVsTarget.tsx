import { useState } from "react";
import { Link } from "react-router-dom";
import { AssetLink } from "./AssetLink";
import { AT_TARGET_PP, type Comparison, type ComparisonRow } from "../lib/comparison";
import { CLASS_LABEL, INVESTABLE_CLASSES } from "../lib/classes";
import { money } from "../lib/format";

/** Mesma matiz por classe do gráfico da Carteira alvo — a cor segue a entidade, e aqui ela
 *  continua significando CLASSE. A polaridade (acima/abaixo do alvo) vem da geometria: o
 *  lado do eixo zero, o sinal do número e o rótulo. Assim nenhuma cor nova precisa ser
 *  inventada e a leitura sobrevive a qualquer tipo de daltonismo. */
const CLASS_HUE: Record<string, string> = {
  STOCK: "var(--viz-stock)",
  FII: "var(--viz-fii)",
  ETF: "var(--viz-etf)",
  BDR: "var(--viz-bdr)",
  RENDA_FIXA: "var(--viz-rf)",
  UNKNOWN: "var(--muted)",
};

const fmt = (n: number) => `${n.toFixed(2).replace(".", ",")}%`;
const signed = (n: number) => `${n > 0 ? "+" : n < 0 ? "−" : ""}${Math.abs(n).toFixed(2).replace(".", ",")}`;

const STATUS_LABEL: Record<ComparisonRow["status"], string> = {
  ok: "no alvo",
  below: "falta comprar",
  above: "acima do alvo",
  off_target: "fora da carteira alvo",
  not_bought: "ainda não comprado",
};

/** Barra 100% da carteira, segmentada por ativo e agrupada por classe (a mesma linguagem
 *  do gráfico da Carteira alvo). `weights` são % sobre o total. */
function StackedBar({
  label,
  groups,
  caption,
}: {
  label: string;
  groups: { cls: string; items: { ticker: string; pct: number }[] }[];
  caption: string;
}) {
  const allocated = groups.reduce((s, g) => s + g.items.reduce((t, i) => t + i.pct, 0), 0);
  const rest = Math.max(0, 100 - allocated);
  return (
    <div className="cmp-bar-block">
      <div className="cmp-bar-head">
        <span className="cmp-bar-label">{label}</span>
        <span className="muted cmp-bar-caption">{caption}</span>
      </div>
      <div className="tp-track" role="img" aria-label={`${label}: ${caption}`}>
        <div className="tp-bar">
          {groups.flatMap((g, gi) =>
            g.items.map((it, i) => (
              <span
                key={`${g.cls}-${it.ticker}`}
                className={`tp-seg ${i === 0 && gi > 0 ? "tp-seg-class" : ""}`}
                style={{
                  flexGrow: Math.max(it.pct, 0.01),
                  background:
                    g.items.length <= 1
                      ? CLASS_HUE[g.cls]
                      : `color-mix(in oklab, ${CLASS_HUE[g.cls]} ${100 - Math.round((i / (g.items.length - 1)) * 42)}%, var(--card))`,
                }}
                title={`${it.ticker} · ${CLASS_LABEL[g.cls] ?? g.cls}: ${fmt(it.pct)} do total`}
              />
            )),
          )}
          {rest > 0.05 && <span className="tp-seg tp-seg-empty" style={{ flexGrow: rest }} />}
        </div>
      </div>
    </div>
  );
}

/** Uma linha do desvio: barra divergente ancorada no zero. À esquerda falta comprar, à
 *  direita está acima do alvo. A régua é comum a todas as linhas. */
function DeviationRow({ row, scale }: { row: ComparisonRow; scale: number }) {
  const width = scale > 0 ? (Math.abs(row.deltaPp) / scale) * 50 : 0; // 50% = meia régua
  const below = row.deltaPp > 0; // alvo maior que o atual => falta comprar
  return (
    <li className={`cmp-row cmp-row-${row.status}`}>
      <span className="cmp-ticker">
        <AssetLink ticker={row.ticker} />
      </span>
      <span className="cmp-axis">
        <span
          className="cmp-fill"
          style={{
            background: CLASS_HUE[row.cls] ?? CLASS_HUE.UNKNOWN,
            width: `${width}%`,
            ...(below ? { right: "50%" } : { left: "50%" }),
          }}
        />
      </span>
      <span className="cmp-nums">
        <span className="cmp-delta">{signed(row.deltaPp)} p.p.</span>
        <span className="muted cmp-detail">
          {fmt(row.currentPct)} → {fmt(row.targetPct)}
        </span>
      </span>
      <span className="cmp-brl">
        <span className={below ? "cmp-brl-buy" : "cmp-brl-over"}>
          {row.status === "ok"
            ? "no alvo"
            : below
              ? `faltam ${money(row.deltaBrl)}`
              : `sobram ${money(Math.abs(row.deltaBrl))}`}
        </span>
        {row.status !== "ok" && row.status !== "below" && row.status !== "above" && (
          <span className="muted cmp-tag">{STATUS_LABEL[row.status]}</span>
        )}
      </span>
    </li>
  );
}

export function PortfolioVsTarget({ comparison }: { comparison: Comparison }) {
  const [showAll, setShowAll] = useState(false);
  const { rows, byClass, targetSumPct, offTargetPct, hasTarget, totalValue } = comparison;

  if (!hasTarget) {
    return (
      <div className="card empty-target">
        <h3>🎯 Defina sua carteira alvo</h3>
        <p className="muted">
          A comparação precisa de um destino: as metas por classe e a composição de cada uma.
          É a mesma configuração que orienta os aportes na aba Plantar.
        </p>
        <Link className="primary" to="/alvo">
          Montar carteira alvo →
        </Link>
      </div>
    );
  }

  const group = (pick: (r: ComparisonRow) => number) =>
    INVESTABLE_CLASSES.map((cls) => ({
      cls,
      items: rows
        .filter((r) => r.cls === cls && pick(r) > 0)
        .sort((a, b) => pick(b) - pick(a))
        .map((r) => ({ ticker: r.ticker, pct: pick(r) })),
    })).filter((g) => g.items.length > 0);

  const offTarget = rows.filter((r) => r.status === "off_target" && r.currentPct > 0);
  const hoje = [
    ...group((r) => (r.status === "off_target" ? 0 : r.currentPct)),
    ...(offTarget.length
      ? [{ cls: "UNKNOWN", items: offTarget.map((r) => ({ ticker: r.ticker, pct: r.currentPct })) }]
      : []),
  ];

  const atTarget = rows.filter((r) => r.status === "ok");
  const acionaveis = rows.filter((r) => r.status !== "ok");
  const visiveis = showAll ? rows : acionaveis;
  const scale = Math.max(...rows.map((r) => Math.abs(r.deltaPp)), 1);

  return (
    <div className="cmp">
      <section className="card cmp-bars">
        <StackedBar
          label="Hoje"
          groups={hoje}
          caption={
            offTargetPct > 0.05
              ? `${fmt(offTargetPct)} fora da carteira alvo`
              : "toda a carteira dentro do alvo"
          }
        />
        <StackedBar
          label="Alvo"
          groups={group((r) => r.targetPct)}
          caption={
            Math.abs(targetSumPct - 100) > 0.5
              ? `metas somam ${fmt(targetSumPct)} — ajuste na Carteira alvo`
              : "metas somam 100%"
          }
        />
      </section>

      <section className="card cmp-list">
        <div className="cmp-list-head">
          <h3>Desvio por ativo</h3>
          <span className="muted cmp-scale">
            falta comprar ← │ → acima do alvo
          </span>
        </div>
        <ul className="cmp-rows">
          {visiveis.map((r) => (
            <DeviationRow key={r.ticker} row={r} scale={scale} />
          ))}
        </ul>
        {atTarget.length > 0 && (
          <button type="button" className="link-button" onClick={() => setShowAll((v) => !v)}>
            {showAll
              ? `▲ Ocultar os ${atTarget.length} que já estão no alvo`
              : `▼ Mostrar também os ${atTarget.length} que já estão no alvo (desvio abaixo de ${String(AT_TARGET_PP).replace(".", ",")} p.p.)`}
          </button>
        )}
      </section>

      <section className="card cmp-list">
        <h3>Desvio por classe</h3>
        <ul className="cmp-rows">
          {byClass
            .filter((b) => b.targetPct > 0 || b.currentPct > 0)
            .map((b) => (
              <li className="cmp-row" key={b.cls}>
                <span className="cmp-ticker cmp-classname">{CLASS_LABEL[b.cls] ?? b.cls}</span>
                <span className="cmp-axis">
                  <span
                    className="cmp-fill"
                    style={{
                      background: CLASS_HUE[b.cls],
                      width: `${(Math.abs(b.deltaPp) / Math.max(...byClass.map((x) => Math.abs(x.deltaPp)), 1)) * 50}%`,
                      ...(b.deltaPp > 0 ? { right: "50%" } : { left: "50%" }),
                    }}
                  />
                </span>
                <span className="cmp-nums">
                  <span className="cmp-delta">{signed(b.deltaPp)} p.p.</span>
                  <span className="muted cmp-detail">
                    {fmt(b.currentPct)} → {fmt(b.targetPct)}
                  </span>
                </span>
                <span className="cmp-brl">
                  <span className={b.deltaPp > 0 ? "cmp-brl-buy" : "cmp-brl-over"}>
                    {Math.abs(b.deltaPp) < AT_TARGET_PP
                      ? "no alvo"
                      : b.deltaPp > 0
                        ? `faltam ${money(b.deltaBrl)}`
                        : `sobram ${money(Math.abs(b.deltaBrl))}`}
                  </span>
                </span>
              </li>
            ))}
        </ul>
        {totalValue > 0 && (
          <p className="muted cmp-note">
            Os dois lados usam o mesmo denominador: {money(totalValue)} de renda variável. A
            reserva fica de fora, como nas metas por classe.
          </p>
        )}
      </section>
    </div>
  );
}
