import { useState } from "react";
import { Link } from "react-router-dom";
import { usePreferences, useSavePreferences } from "../api/queries";
import { AssetLink } from "./AssetLink";
import { AT_TARGET_PP, type Comparison, type ComparisonRow } from "../lib/comparison";
import { ALLOCATION_CLASSES, byWeightDesc, CLASS_LABEL, RENDA_FIXA } from "../lib/classes";
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

/** Barra 100% da carteira, segmentada por ativo e agrupada por classe (a mesma linguagem
 *  do gráfico da Carteira alvo). `pct` são % sobre o mesmo denominador da barra. */
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
                title={`${it.ticker} · ${CLASS_LABEL[g.cls] ?? g.cls}: ${fmt(it.pct)}`}
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
 *  direita está acima do alvo. Só entram aqui linhas COM alvo — o legado tem seção própria,
 *  porque medir desvio contra alvo zero não é um número pequeno, é um número que não existe. */
function DeviationRow({ row, scale }: { row: ComparisonRow; scale: number }) {
  const deltaPp = row.deltaPp ?? 0;
  const width = scale > 0 ? (Math.abs(deltaPp) / scale) * 50 : 0; // 50% = meia régua
  const below = deltaPp > 0; // alvo maior que o atual => falta comprar
  return (
    <li className={`cmp-row cmp-row-${row.state.toLowerCase()}`}>
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
        <span className="cmp-delta">{signed(deltaPp)} p.p.</span>
        <span className="muted cmp-detail">
          {fmt(row.currentPct)} → {fmt(row.targetPct ?? 0)}
        </span>
      </span>
      <span className="cmp-brl">
        <span className={below ? "cmp-brl-buy" : "cmp-brl-over"}>
          {row.status === "ok"
            ? "no alvo"
            : below
              ? `faltam ${money(row.deltaBrl ?? 0)}`
              : `sobram ${money(Math.abs(row.deltaBrl ?? 0))}`}
        </span>
        {row.state === "NEW" && <span className="muted cmp-tag">ainda não comprado</span>}
      </span>
    </li>
  );
}

/** Acesso à Carteira alvo a partir da Carteira. Quando ela está vazia ou não soma 100%,
 *  este bloco vira o call-to-action principal da página: sem destino não há comparação, e
 *  esconder isso atrás de um link pequeno na aba Plantar era o que fazia o problema
 *  sobreviver. */
function TargetAccess({ comparison }: { comparison: Comparison }) {
  const { hasTarget, targetSumPct } = comparison;
  const desbalanceado = Math.abs(targetSumPct - 100) > 0.5;
  const problema = !hasTarget
    ? "Nenhuma classe tem composição definida."
    : desbalanceado
      ? `As metas por classe somam ${fmt(targetSumPct)}, não 100%.`
      : null;

  if (problema) {
    return (
      <div className="card empty-target">
        <h3>Ajuste sua carteira alvo</h3>
        <p className="muted">{problema}</p>
        <Link className="primary" to="/alvo">
          Abrir carteira alvo →
        </Link>
      </div>
    );
  }

  return (
    <div className="cmp-access">
      {/* Secundário, não primário: quando este bloco aparece a carteira alvo JÁ está
          configurada — é atalho de navegação, não a decisão da tela. O verde sólido fica
          com o empty-target acima, que é o caso em que há mesmo o que decidir. */}
      <Link className="btn-secondary cmp-access-btn" to="/alvo">
        Editar carteira alvo
      </Link>
    </div>
  );
}

/** Controle do que entra na base dos alvos em R$. Fica VISÍVEL, e não escondido em
 *  "ajustes avançados", porque ele muda o que a tela responde: com o legado na base, a
 *  carteira segue subalocada até a venda — que é o retrato aritmeticamente honesto. */
function LegacyBaseToggle({ comparison }: { comparison: Comparison }) {
  const prefs = usePreferences();
  const savePrefs = useSavePreferences();
  const { legacyValue, legacyInTotal } = comparison;
  if (legacyValue <= 0) return null;

  return (
    <label className="class-chip class-chip-wide cmp-legacy-toggle">
      <input
        type="checkbox"
        checked={prefs.data?.legacy_in_total ?? legacyInTotal}
        disabled={savePrefs.isPending}
        onChange={(e) => savePrefs.mutate({ legacy_in_total: e.target.checked })}
      />
      <span>
        <span className="class-chip-name">Incluir o que está fora do alvo na base</span>
        <span className="class-chip-meta">
          {legacyInTotal
            ? `Alvos em R$ sobre ${money(comparison.targetBase)}. Subalocada até a venda.`
            : `Alvos em R$ sobre os ${money(comparison.alignedValue)} alinhados.`}
        </span>
      </span>
    </label>
  );
}

/** Seção própria das posições fora do alvo. Sem razão ao alvo, sem barra de progresso:
 *  o que existe é valor em R$, participação no patrimônio e o rótulo do estado. */
function OffTargetSection({ comparison }: { comparison: Comparison }) {
  const { legacy, legacyValue, legacyPct, totalValue } = comparison;
  if (legacy.length === 0) return null;
  return (
    <section className="card cmp-list cmp-legacy">
      <div className="cmp-list-head">
        <h3>Fora do alvo</h3>
        <span className="muted cmp-scale">
          {money(legacyValue)} · {fmt(legacyPct)} do patrimônio
        </span>
      </div>
      <ul className="cmp-rows">
        {legacy.map((r) => (
          <li className="cmp-row cmp-row-legacy" key={r.ticker}>
            <span className="cmp-ticker">
              <AssetLink ticker={r.ticker} />
            </span>
            <span className="muted cmp-legacy-class">{CLASS_LABEL[r.cls] ?? r.cls}</span>
            <span className="cmp-brl">
              <span>{money(r.currentValue)}</span>
              <span className="muted cmp-detail">{fmt(r.portfolioPct)} do patrimônio</span>
            </span>
          </li>
        ))}
      </ul>
      <p className="muted cmp-note">
        Sem peso no alvo. Incluídos no total de {money(totalValue)}.
      </p>
      <LegacyBaseToggle comparison={comparison} />
    </section>
  );
}

export function PortfolioVsTarget({ comparison }: { comparison: Comparison }) {
  const [showAll, setShowAll] = useState(false);
  const {
    rows,
    byClass,
    targetSumPct,
    hasTarget,
    alignedValue,
    legacyValue,
    legacyPct,
    legacyInTotal,
    targetBase,
  } = comparison;

  if (!hasTarget) {
    return (
      <div className="cmp">
        <div className="card empty-target">
          <h3>Defina sua carteira alvo</h3>
          <p className="muted">
            Metas por classe e composição de cada uma.
          </p>
          <Link className="primary" to="/alvo">
            Montar carteira alvo →
          </Link>
        </div>
        <OffTargetSection comparison={comparison} />
      </div>
    );
  }

  // Uma ordem só para as DUAS barras: se "Hoje" e "Alvo" se ordenassem cada uma pelo seu
  // próprio peso, elas deixariam de ser comparáveis lado a lado — que é a única razão de
  // estarem coladas. A ordem sai do alvo, com o valor atual como desempate.
  const pesoDaClasse = (cls: string) => {
    const b = byClass.find((x) => x.cls === cls);
    return b?.targetPct || b?.currentPct || 0;
  };
  const barOrder = byWeightDesc(ALLOCATION_CLASSES, pesoDaClasse);

  const group = (pick: (r: ComparisonRow) => number) =>
    barOrder.map((cls) => ({
      cls,
      items: rows
        .filter((r) => r.cls === cls && pick(r) > 0)
        .sort((a, b) => pick(b) - pick(a))
        .map((r) => ({ ticker: r.ticker, pct: pick(r) })),
    })).filter((g) => g.items.length > 0);

  // A renda fixa não tem linha por ticker (os itens da cesta são indexadores), então ela
  // entra nas barras como um bloco único da classe.
  const rf = byClass.find((b) => b.cls === RENDA_FIXA);
  const rfBar = (pct: number) =>
    pct > 0 ? [{ cls: RENDA_FIXA, items: [{ ticker: "Renda fixa", pct }] }] : [];

  const atTarget = rows.filter((r) => r.status === "ok");
  const acionaveis = rows.filter((r) => r.status !== "ok");
  const visiveis = showAll ? rows : acionaveis;
  const scale = Math.max(...rows.map((r) => Math.abs(r.deltaPp ?? 0)), 1);

  return (
    <div className="cmp">
      <TargetAccess comparison={comparison} />

      <section className="card cmp-bars">
        <StackedBar
          label="Hoje"
          groups={[...group((r) => r.currentPct), ...rfBar(rf?.currentPct ?? 0)]}
          caption={
            legacyPct > 0.05
              ? `${money(alignedValue)} seguindo a estratégia`
              : "toda a carteira dentro do alvo"
          }
        />
        <StackedBar
          label="Alvo"
          groups={[...group((r) => r.targetPct ?? 0), ...rfBar(rf?.targetPct ?? 0)]}
          caption={
            Math.abs(targetSumPct - 100) > 0.5
              ? `metas somam ${fmt(targetSumPct)} — ajuste na Carteira alvo`
              : "metas somam 100%"
          }
        />
        {legacyPct > 0.05 && (
          <p className="muted cmp-note">
            Barras sobre o capital alinhado. {money(legacyValue)} fora do alvo, abaixo.
          </p>
        )}
      </section>

      <section className="card cmp-list">
        <div className="cmp-list-head">
          <h3>Desvio por ativo</h3>
          <span className="muted cmp-scale">falta comprar ← │ → acima do alvo</span>
        </div>
        <ul className="cmp-rows">
          {visiveis.map((r) => (
            <DeviationRow key={r.ticker} row={r} scale={scale} />
          ))}
        </ul>
        {atTarget.length > 0 && (
          <button type="button" className="link-button" onClick={() => setShowAll((v) => !v)}>
            {showAll
              ? `Ocultar os ${atTarget.length} que já estão no alvo`
              : `Mostrar os ${atTarget.length} que já estão no alvo`}
          </button>
        )}
      </section>

      <OffTargetSection comparison={comparison} />

      <section className="card cmp-list">
        <h3>Desvio por classe</h3>
        <ul className="cmp-rows">
          {byWeightDesc(byClass, (b) => Math.abs(b.deltaPp))
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
        <p className="muted cmp-note">
          Percentuais sobre {money(alignedValue)} (o capital alinhado); valores em R$ sobre{" "}
          {money(targetBase)}
          {legacyValue > 0 &&
            (legacyInTotal
              ? ", que inclui o que está fora do alvo — por isso a carteira segue subalocada até a venda."
              : ", que exclui o que está fora do alvo.")}
        </p>
      </section>
    </div>
  );
}
