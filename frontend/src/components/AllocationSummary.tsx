import type { PlanResponse } from "../types";
import { Tooltip } from "./Tooltip";

/** Mostra alocação atual vs alvo por classe — base do rebalanceamento. */
export function AllocationSummary({ plan }: { plan: PlanResponse }) {
  const classes = Array.from(
    new Set([...Object.keys(plan.targets_by_class), ...Object.keys(plan.current_by_class)]),
  );
  return (
    <div className="alloc">
      <h3>
        <Tooltip metricKey="rebalance_gap">
          <span>Alocação atual vs sua meta</span>
        </Tooltip>
      </h3>
      <div className="alloc-rows">
        {classes.map((c) => {
          const cur = (plan.current_by_class[c] ?? 0) * 100;
          const tgt = (plan.targets_by_class[c] ?? 0) * 100;
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
