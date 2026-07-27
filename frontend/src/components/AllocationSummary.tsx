import type { PlanResponse } from "../types";
import { Tooltip } from "./Tooltip";

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
              <span className="alloc-class">{c}</span>
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
    </div>
  );
}
