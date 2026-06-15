import type { Metric } from "../types";
import { Tooltip } from "./Tooltip";

/** Renderiza uma métrica: rótulo (com tooltip), valor e barra do quanto contribuiu. */
export function MetricValue({ metric }: { metric: Metric }) {
  const pct = metric.normalized != null ? Math.round(metric.normalized * 100) : null;
  return (
    <div className={`metric ${metric.available ? "" : "metric-na"}`}>
      <div className="metric-head">
        <Tooltip metricKey={metric.key}>
          <span className="metric-label">{metric.label}</span>
        </Tooltip>
        <span className="metric-raw">
          {metric.available ? metric.display ?? "—" : "sem dado"}
        </span>
      </div>
      {metric.available && pct != null && (
        <div className="metric-bar" title={`Nota neste critério: ${pct}/100`}>
          <div className="metric-bar-fill" style={{ width: `${pct}%` }} />
          <span className="metric-bar-meta">
            nota {pct} · peso {Math.round(metric.weight * 100)}%
          </span>
        </div>
      )}
      {metric.fallback_used && (
        <div className="metric-fallback">aproximação: {metric.fallback_used}</div>
      )}
    </div>
  );
}
