import { useState } from "react";
import { Link } from "react-router-dom";
import { usePreferences, useSavePreferences } from "../api/queries";
import { AssetLink } from "./AssetLink";
import { AT_TARGET_PP, type Comparison, type ComparisonRow } from "../lib/comparison";
import { byWeightDesc, CLASS_LABEL } from "../lib/classes";
import { money, pctPts, signedPp } from "../lib/format";
import { classHue } from "../lib/viz";

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
            background: classHue(row.cls),
            width: `${width}%`,
            ...(below ? { right: "50%" } : { left: "50%" }),
          }}
        />
      </span>
      <span className="cmp-nums">
        <span className="cmp-delta">{signedPp(deltaPp, 2)}</span>
        <span className="muted cmp-detail">
          {pctPts(row.currentPct, 2)} → {pctPts(row.targetPct ?? 0, 2)}
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
      ? `As metas por classe somam ${pctPts(targetSumPct, 2)}, não 100%.`
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
          {money(legacyValue)} · {pctPts(legacyPct, 2)} do patrimônio
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
              <span className="muted cmp-detail">{pctPts(r.portfolioPct, 2)} do patrimônio</span>
            </span>
          </li>
        ))}
      </ul>
      <p className="muted cmp-note">Sem peso no alvo. Incluídos no total de {money(totalValue)}.</p>
      <LegacyBaseToggle comparison={comparison} />
    </section>
  );
}

export function PortfolioVsTarget({ comparison }: { comparison: Comparison }) {
  const [showAll, setShowAll] = useState(false);
  const { rows, byClass, hasTarget, alignedValue, legacyValue, legacyInTotal, targetBase } =
    comparison;

  if (!hasTarget) {
    return (
      <div className="cmp">
        <div className="card empty-target">
          <h3>Defina sua carteira alvo</h3>
          <p className="muted">Metas por classe e composição de cada uma.</p>
          <Link className="primary" to="/alvo">
            Montar carteira alvo →
          </Link>
        </div>
        <OffTargetSection comparison={comparison} />
      </div>
    );
  }

  const atTarget = rows.filter((r) => r.status === "ok");
  const acionaveis = rows.filter((r) => r.status !== "ok");
  const visiveis = showAll ? rows : acionaveis;
  const scale = Math.max(...rows.map((r) => Math.abs(r.deltaPp ?? 0)), 1);

  return (
    <div className="cmp">
      <TargetAccess comparison={comparison} />

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
                      background: classHue(b.cls),
                      width: `${(Math.abs(b.deltaPp) / Math.max(...byClass.map((x) => Math.abs(x.deltaPp)), 1)) * 50}%`,
                      ...(b.deltaPp > 0 ? { right: "50%" } : { left: "50%" }),
                    }}
                  />
                </span>
                <span className="cmp-nums">
                  <span className="cmp-delta">{signedPp(b.deltaPp, 2)}</span>
                  <span className="muted cmp-detail">
                    {pctPts(b.currentPct, 2)} → {pctPts(b.targetPct, 2)}
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
