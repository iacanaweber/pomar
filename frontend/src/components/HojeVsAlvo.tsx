import { AT_TARGET_PP, type Comparison, type ComparisonRow } from "../lib/comparison";
import { ALLOCATION_CLASSES, byWeightDesc, CLASS_LABEL, RENDA_FIXA } from "../lib/classes";
import { money, pctPts, signedPp } from "../lib/format";
import { classHue, step } from "../lib/viz";

/** "Onde estou" contra "onde eu quis estar", em duas barras e uma tabela.
 *
 *  A barra de HOJE cobre o patrimônio INTEIRO — inclusive o que não tem alvo. A de ALVO
 *  cobre as metas. A diferença entre as duas É a mensagem: uma classe que existe só na
 *  primeira é capital fora da estratégia, e ela precisa estar visível para ser vendida
 *  aos poucos. Antes, o legado era descartado das duas barras e as classes restantes
 *  inflavam até preencher o trilho — o buraco não aparecia.
 *
 *  Mesmo objeto no Plantar e na Carteira, de propósito: é a mesma pergunta. */

/** Barra 100%, segmentada por ativo e agrupada por classe. Os `pct` de cada item têm de
 *  compartilhar o denominador da barra — quem monta os grupos garante isso. */
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
                  background: step(classHue(g.cls), i, g.items.length),
                }}
                title={`${it.ticker} · ${CLASS_LABEL[g.cls] ?? g.cls}: ${pctPts(it.pct, 2)}`}
              />
            )),
          )}
          {rest > 0.05 && <span className="tp-seg tp-seg-empty" style={{ flexGrow: rest }} />}
        </div>
      </div>
    </div>
  );
}

export function HojeVsAlvo({
  comparison,
  coberturaLegado,
  gapLegado,
}: {
  comparison: Comparison;
  /** Fração do gap que a venda do legado cobriria (0..1+), quando o plano calculou.
   *  Aritmética, NÃO sugestão de venda — o app não recomenda vender nada. */
  coberturaLegado?: number | null;
  gapLegado?: number | null;
}) {
  const { rows, legacy, byClass, totalValue, legacyValue, legacyPct, targetSumPct, hasTarget } =
    comparison;

  if (!hasTarget) {
    return (
      <section className="card cmp-bars">
        <h3 className="cmp-vazio-titulo">Sem carteira alvo</h3>
        <p className="muted">Defina as metas por classe e o Plantar passa a dizer onde aportar.</p>
      </section>
    );
  }

  // Uma ordem só para as DUAS barras: se cada uma se ordenasse pelo próprio peso, elas
  // deixariam de ser comparáveis lado a lado — que é a única razão de estarem coladas.
  const pesoDaClasse = (cls: string) => {
    const b = byClass.find((x) => x.cls === cls);
    return b?.targetPct || b?.currentPct || 0;
  };
  const barOrder = byWeightDesc(ALLOCATION_CLASSES, pesoDaClasse);

  const agrupar = (linhas: ComparisonRow[], pick: (r: ComparisonRow) => number) =>
    barOrder
      .map((cls) => ({
        cls,
        items: linhas
          .filter((r) => r.cls === cls && pick(r) > 0)
          .sort((a, b) => pick(b) - pick(a))
          .map((r) => ({ ticker: r.ticker, pct: pick(r) })),
      }))
      .filter((g) => g.items.length > 0);

  // A renda fixa não tem linha por ticker (os itens da cesta dela são indexadores), então
  // entra nas barras como bloco único da classe.
  const rf = byClass.find((b) => b.cls === RENDA_FIXA);
  const rfBar = (pct: number) =>
    pct > 0 ? [{ cls: RENDA_FIXA, items: [{ ticker: "Renda fixa", pct }] }] : [];

  // HOJE: `[...rows, ...legacy]` com `portfolioPct` — fatia do patrimônio. É o que faz as
  // ações fora do alvo aparecerem, e o que faz a barra fechar 100% de verdade.
  const hoje = [
    ...agrupar([...rows, ...legacy], (r) => r.portfolioPct),
    ...rfBar(rf?.currentPct ?? 0),
  ];
  // ALVO: só quem tem alvo, e `targetPct` já é % do total.
  const alvo = [...agrupar(rows, (r) => r.targetPct ?? 0), ...rfBar(rf?.targetPct ?? 0)];

  const classes = byClass.filter((b) => b.targetPct > 0 || b.currentValue > 0);

  return (
    <section className="card cmp-bars">
      <StackedBar label="Hoje" groups={hoje} caption={money(totalValue)} />
      <StackedBar
        label="Alvo"
        groups={alvo}
        caption={
          Math.abs(targetSumPct - 100) > 0.5
            ? `metas somam ${pctPts(targetSumPct, 2)} — ajuste na Carteira alvo`
            : "metas somam 100%"
        }
      />
      {legacyPct > 0.05 && (
        <p className="muted cmp-note">
          {money(legacyValue)} ({pctPts(legacyPct)}) sem alvo definido — aparece em Hoje e não em
          Alvo.
          {coberturaLegado != null && gapLegado != null && gapLegado > 0 && (
            <>
              {" "}
              Vender tudo cobriria <strong>
                {pctPts(Math.min(coberturaLegado, 1) * 100, 0)}
              </strong>{" "}
              do que falta ({money(gapLegado)}){coberturaLegado > 1 && ", com sobra"}.
            </>
          )}
        </p>
      )}
      <TabelaPorClasse classes={classes} />
    </section>
  );
}

/** A tabela dá o número que a barra resume. `<table>` de verdade com `scope`: é dado
 *  tabular, e um `<ul>` de grid nunca deu a coluna a quem usa leitor de tela. */
function TabelaPorClasse({ classes }: { classes: Comparison["byClass"] }) {
  return (
    <div className="cmp-tabela-wrap">
      <table className="cmp-tabela">
        <caption className="sr-only">Composição de hoje contra a carteira alvo, por classe</caption>
        <thead>
          <tr>
            <th scope="col">Classe</th>
            <th scope="col">Hoje</th>
            <th scope="col">Alvo</th>
            <th scope="col">Desvio</th>
            <th scope="col">Falta</th>
          </tr>
        </thead>
        <tbody>
          {classes.map((c) => {
            const noAlvo = Math.abs(c.deltaPp) < AT_TARGET_PP;
            return (
              <tr key={c.cls}>
                <th scope="row">
                  <span className="cmp-marca" style={{ background: classHue(c.cls) }} />
                  {CLASS_LABEL[c.cls] ?? c.cls}
                </th>
                <td>{pctPts(c.currentPct)}</td>
                <td className="muted">{pctPts(c.targetPct)}</td>
                <td>{noAlvo ? <span className="muted">no alvo</span> : signedPp(-c.deltaPp)}</td>
                <td>
                  {noAlvo ? (
                    <span className="muted">—</span>
                  ) : c.deltaPp > 0 ? (
                    /* Quente = agir. É a cor mais alta da interface e só aparece onde
                       dinheiro deve ir. */
                    <span className="cmp-plantar">{money(c.deltaBrl)}</span>
                  ) : (
                    <span className="cmp-sobra">sobra {money(Math.abs(c.deltaBrl))}</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
