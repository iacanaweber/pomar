import { pct } from "../lib/format";
import { Tooltip } from "./Tooltip";

/**
 * Mostra DY de mercado + Yield on Cost lado a lado. Seta ↑ quando o YoC supera o DY
 * de mercado (a posição "rende mais" sobre o que você pagou). Sem custo → "—".
 */
export function YocCell({
  dividendYield,
  yieldOnCost,
}: {
  dividendYield?: number | null;
  yieldOnCost?: number | null;
}) {
  return (
    <span className="yoc-cell">
      {dividendYield != null && <span className="yoc-dy">DY {pct(dividendYield)}</span>}
      <Tooltip metricKey="yield_on_cost">
        <span className="yoc-yoc">
          {yieldOnCost != null ? (
            <>
              YoC {pct(yieldOnCost)}
              {dividendYield != null && yieldOnCost > dividendYield ? (
                <span className="yoc-up" aria-label="acima do DY de mercado">
                  {" "}
                  ↑
                </span>
              ) : null}
            </>
          ) : (
            <span className="muted">YoC —</span>
          )}
        </span>
      </Tooltip>
    </span>
  );
}
