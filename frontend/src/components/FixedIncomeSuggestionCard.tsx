import { Link } from "react-router-dom";
import type { FixedIncomeSuggestion } from "../types";
import { money, pct } from "../lib/format";
import { Tooltip } from "./Tooltip";

const fmtPp = (n: number) => `${n.toFixed(1).replace(".", ",")} p.p.`;

/** A parcela de renda fixa do aporte — o primeiro degrau da cascata, e por isso o
 *  primeiro card da tela.
 *
 *  Não há quantidade de cotas aqui: a compra de renda fixa é manual e feita fora do app,
 *  então a saída é uma INSTRUÇÃO em reais. O que o app pode fazer é poupar a redigitação,
 *  levando direto ao lançamento do novo saldo na conta sugerida.
 *
 *  O piso e o peso da classe aparecem separados de propósito: são perguntas diferentes —
 *  "quanto eu consigo sacar hoje" e "quanto da carteira está em renda fixa" — e uma
 *  aplicação travada responde só à segunda.
 */
export function FixedIncomeSuggestionCard({
  suggestion,
  currency = "BRL",
}: {
  suggestion: FixedIncomeSuggestion;
  currency?: string;
}) {
  const {
    directed_now: total = 0,
    floor_part: piso = 0,
    weight_part: peso = 0,
    gap_brl: gap = 0,
    gap_pp: gapPp = 0,
    current_value: atual = 0,
    target_amount: alvo = 0,
    by_indexer: porIndexador = [],
    note,
  } = suggestion;

  const noAlvo = gap <= 0;

  return (
    <section className="alloc fi-suggestion">
      <div className="goal-head">
        <Tooltip metricKey="reserve_floor">
          <h3 style={{ margin: 0 }}>1. Renda fixa</h3>
        </Tooltip>
        <strong className={total > 0 ? "fi-amount" : "muted"}>
          {total > 0 ? money(total, currency) : "nada neste aporte"}
        </strong>
      </div>

      {total > 0 && (piso > 0 || peso > 0) && (
        <ul className="fi-parts">
          {piso > 0 && (
            <li>
              <span className="muted">Piso da reserva</span>
              <strong>{money(piso, currency)}</strong>
            </li>
          )}
          {peso > 0 && (
            <li>
              <span className="muted">Peso da classe</span>
              <strong>{money(peso, currency)}</strong>
            </li>
          )}
        </ul>
      )}

      <p className="goal-status" style={{ margin: "6px 0 0" }}>
        {noAlvo ? (
          <span className="risk-verde">✓ No alvo ou acima — nada a aplicar aqui.</span>
        ) : (
          <>
            Faltam <strong>{money(gap, currency)}</strong> ({fmtPp(gapPp)}) para a meta de{" "}
            {money(alvo, currency)}; hoje há {money(atual, currency)}.
          </>
        )}
      </p>

      {porIndexador.length > 0 && (
        <ul className="fi-indexers">
          {porIndexador.map((i) => (
            <li key={i.code}>
              <span className="fi-indexer-name">
                {i.name}
                {i.target_pct ? (
                  <span className="muted"> · alvo {pct(i.target_pct)} da classe</span>
                ) : null}
              </span>
              <strong>{money(i.amount ?? 0, currency)}</strong>
              {i.account_id ? (
                // atalho para não redigitar o que o app já sabe: abre a conta sugerida
                <Link className="link-button fi-shortcut" to={`/reserva?conta=${i.account_id}`}>
                  lançar em {i.account_name} →
                </Link>
              ) : (
                <Link className="link-button fi-shortcut" to="/reserva">
                  escolher a conta →
                </Link>
              )}
            </li>
          ))}
        </ul>
      )}

      {note && (
        <p className="note-desc" style={{ margin: "6px 0 0" }}>
          {note}
        </p>
      )}
    </section>
  );
}
