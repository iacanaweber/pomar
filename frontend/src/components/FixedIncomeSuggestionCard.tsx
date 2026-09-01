import { Link } from "react-router-dom";
import type { FixedIncomeSuggestion, ReserveSuggestion } from "../types";
import { money, num, pct } from "../lib/format";
import { useComprasFeitas } from "../hooks/useComprasFeitas";
import { Tooltip } from "./Tooltip";

/** A parcela de renda fixa do aporte: o que fazer com ela, linha a linha.
 *
 *  Não há mais um resumo "piso × peso" acima da lista. Ele existia porque as linhas não
 *  distinguiam um do outro; agora a primeira linha É o piso, e repetir o mesmo número duas
 *  vezes no mesmo cartão só faz procurar a diferença entre eles.
 *
 *  Três formas de linha, porque são três formas de cumprir a instrução. O PISO é um valor
 *  só, a lançar numa conta de resgate imediato: qual conta é decisão do dono da carteira,
 *  e apontar a maior com determinada tag poderia apontar uma aplicação travada, que não
 *  serve de reserva. A TAG de indexador vira instrução em reais com o atalho para a conta
 *  que já tem aquela tag, para não redigitar o que o app já sabe. O TICKER (um ETF de
 *  renda fixa) vira cotas e preço, porque se executa na corretora como qualquer outra
 *  compra — e por isso traz o registro de ordem junto.
 *
 *  O piso e o peso da classe aparecem separados de propósito: são perguntas diferentes —
 *  "quanto eu consigo sacar hoje" e "quanto da carteira está em renda fixa" — e uma
 *  aplicação travada responde só à segunda.
 */
/** Barra do piso: reserva LÍQUIDA contra o piso corrigido. Fica aqui dentro, e não num
 *  card próprio, porque duas caixas falando do mesmo número na mesma tela é o que faz o
 *  usuário procurar a diferença entre elas. */
function FloorBar({ reserve, currency }: { reserve: ReserveSuggestion; currency: string }) {
  const filled = Math.min(Math.round((reserve.pct_filled ?? 0) * 100), 100);
  const corrigido = reserve.floor_index === "ipca" && reserve.floor_index_available;
  return (
    <div className="fi-floor">
      <div
        className="goal-bar"
        role="progressbar"
        aria-valuenow={filled}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Reserva líquida: ${filled}% do piso`}
      >
        <div className="alloc-track" style={{ height: 16 }}>
          <div
            className="alloc-cur"
            style={{
              width: `${filled}%`,
              background: (reserve.gap ?? 0) > 0 ? "var(--leaf)" : "var(--green)",
            }}
          />
        </div>
        <span className="goal-bar-label">
          Piso: {money(reserve.current_amount ?? 0, currency)} de{" "}
          {money(reserve.target_amount ?? 0, currency)} · {filled}%
          {corrigido && " (corrigido pelo IPCA)"}
          {reserve.floor_index === "ipca" &&
            !reserve.floor_index_available &&
            " (IPCA indisponível — valor nominal)"}
        </span>
      </div>
    </div>
  );
}

export function FixedIncomeSuggestionCard({
  suggestion,
  reserve,
  currency = "BRL",
  planId,
}: {
  suggestion: FixedIncomeSuggestion;
  reserve?: ReserveSuggestion | null;
  currency?: string;
  /** Escopa o checklist de conferência: aporte novo começa com a lista limpa. */
  planId?: number | null;
}) {
  const comprei = useComprasFeitas(planId);
  const {
    directed_now: total = 0,
    gap_brl: gap = 0,
    gap_pp: gapPp = 0,
    current_value: atual = 0,
    target_amount: alvo = 0,
    by_indexer: porIndexador = [],
    note,
  } = suggestion;

  const noAlvo = gap <= 0;
  // Sem nada a dirigir, o cartão volta à superfície neutra: ele ainda confirma que a renda
  // fixa foi considerada, mas quem chama atenção é a instrução, não a confirmação. Mesma
  // regra de `.reserve-goal.goal-met`.
  const quiet = total <= 0;

  return (
    <section className={`alloc fi-suggestion${quiet ? " fi-quiet" : ""}`}>
      <div className="goal-head">
        <h3 style={{ margin: 0 }}>
          <Tooltip metricKey="reserve_floor">
            <span>Renda fixa</span>
          </Tooltip>
        </h3>
        <strong className={total > 0 ? "fi-amount" : "muted"}>
          {total > 0 ? money(total, currency) : "nada neste aporte"}
        </strong>
      </div>

      {reserve && <FloorBar reserve={reserve} currency={currency} />}

      <p className="goal-status" style={{ margin: "6px 0 0" }}>
        {noAlvo ? (
          // "nada a aplicar aqui" só é verdade quando não há linha nenhuma abaixo. O gap
          // aqui é o do PESO da classe, e o PISO pode estar em déficit ao mesmo tempo —
          // uma carteira 61% em renda fixa com metade da reserva líquida é exatamente isso.
          // Sem a distinção, o cartão negava, uma linha acima, os R$ 1.800 que ele mandava
          // lançar.
          <span className="risk-verde">
            ✓ Peso da classe no alvo ou acima{quiet ? " — nada a aplicar aqui." : "."}
          </span>
        ) : (
          <>
            Faltam <strong>{money(gap, currency)}</strong> ({num(gapPp, 1)} p.p.) para a meta de{" "}
            {money(alvo, currency)}; hoje há {money(atual, currency)}.
          </>
        )}
      </p>

      {porIndexador.length > 0 && (
        <ul className="fi-indexers">
          {porIndexador.map((i) => (
            <li key={i.code} className={i.kind === "floor" ? "fi-line-floor" : undefined}>
              <span className="fi-indexer-name">
                {i.kind === "ticker" && i.ticker ? i.ticker : i.name}
                {i.target_pct ? (
                  <span className="muted"> · alvo {pct(i.target_pct)} da classe</span>
                ) : null}
              </span>
              <strong>{money(i.amount ?? 0, currency)}</strong>
              {i.kind === "floor" ? (
                // sem conta apontada: a escolha é do usuário, e a única exigência é a
                // liquidez — uma aplicação travada não responde por uma emergência
                <Link className="link-button fi-shortcut" to="/reserva">
                  lançar numa conta de resgate imediato →
                </Link>
              ) : i.kind === "ticker" && i.ticker ? (
                // cotas e preço, e não "lance em conta": esta compra é da corretora
                <>
                  <Link className="link-button fi-shortcut" to={`/ativo/${i.ticker}`}>
                    {i.shares ?? 0} × {i.price ? money(i.price, currency) : "—"} →
                  </Link>
                  <label className={`card-ack ${comprei.feito(i.ticker) ? "card-ack-on" : ""}`}>
                    <input
                      type="checkbox"
                      checked={comprei.feito(i.ticker)}
                      onChange={() => comprei.alternar(i.ticker!)}
                    />
                    <span>já comprei</span>
                  </label>
                </>
              ) : i.account_id ? (
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
