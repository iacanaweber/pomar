import { Link } from "react-router-dom";
import type { PlanResponse } from "../types";
import { classLabel } from "../lib/classes";
import { money, pct } from "../lib/format";
import { Tooltip } from "./Tooltip";

/** Uma linha de ARITMÉTICA sobre os ativos fora do alvo — não uma sugestão de venda.
 *
 *  O app não recomenda vender nada. O que ele responde é quanto do buraco atual já está
 *  em capital que não segue mais a estratégia, porque é a única parte dessa conta que o
 *  usuário não faz de cabeça. */
function LegacyLine({ plan }: { plan: PlanResponse }) {
  const legacy = plan.legacy;
  if (!legacy || (legacy.value ?? 0) <= 0) return null;
  const cobertura = legacy.gap_coverage;
  const tickers = legacy.tickers ?? [];
  return (
    <p className="alloc-legend plan-legacy">
      <strong>{money(legacy.value ?? 0, plan.currency)}</strong> em ativos fora do alvo (
      {tickers.slice(0, 4).join(", ")}
      {tickers.length > 4 ? ` e mais ${tickers.length - 4}` : ""})
      {cobertura != null ? (
        <>
          {" "}
         . Vendê-los cobriria <strong>{pct(Math.min(cobertura, 1))}</strong> do gap de{" "}
          {money(legacy.gap ?? 0, plan.currency)}
          {cobertura > 1 && " (com sobra)"}.
        </>
      ) : (
        <>. Sem gap a cobrir.</>
      )}{" "}
      <Link to="/carteira">ver na Carteira →</Link>
    </p>
  );
}

/** Mostra alocação atual vs alvo por classe — base do rebalanceamento. */
export function AllocationSummary({ plan }: { plan: PlanResponse }) {
  const targetsByClass = plan.targets_by_class ?? {};
  const currentByClass = plan.current_by_class ?? {};
  // Classe com meta 0% E sem posição é ruído ("0% / alvo 0%"). Com meta 0% mas com
  // posição ela FICA: é justamente o que precisa ser desinvestido.
  const classes = Array.from(
    new Set([...Object.keys(targetsByClass), ...Object.keys(currentByClass)]),
  ).filter((c) => (targetsByClass[c] ?? 0) > 0 || (currentByClass[c] ?? 0) > 0);
  return (
    <div className="alloc">
      <h3>
        <Tooltip metricKey="rebalance_gap">
          <span>Alocação atual vs sua meta</span>
        </Tooltip>
      </h3>
      <div className="alloc-rows">
        {classes.map((c) => {
          const cur = (currentByClass[c] ?? 0) * 100;
          const tgt = (targetsByClass[c] ?? 0) * 100;
          return (
            <div className="alloc-row" key={c}>
              <span className="alloc-class">{classLabel(c)}</span>
              <div className="alloc-track">
                <div className="alloc-cur" style={{ width: `${Math.min(cur, 100)}%` }} />
                <div className="alloc-tgt" style={{ left: `${Math.min(tgt, 100)}%` }} />
              </div>
              <span className="alloc-nums">
                {cur.toFixed(0)}% <span className="muted">/ alvo {tgt.toFixed(0)}%</span>
              </span>
            </div>
          );
        })}
      </div>
      <p className="alloc-legend">
        <span className="dot dot-cur" /> atual &nbsp; <span className="dot dot-tgt" /> meta
      </p>
      <LegacyLine plan={plan} />
    </div>
  );
}
