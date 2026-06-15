import { MetricValue } from "./MetricValue";
import type { ScoredAsset } from "../types";

/** Decomposição expansível do score de um ativo — todas as métricas e suas fontes. */
export function ScoreBreakdown({ asset }: { asset: ScoredAsset }) {
  return (
    <div className="breakdown">
      <div className="breakdown-grid">
        {asset.metrics.map((m) => (
          <MetricValue key={m.key} metric={m} />
        ))}
      </div>
      <p className="breakdown-note">
        Completude dos dados: <strong>{asset.data_completeness}</strong>. Métricas sem dado não
        entram no score (o peso é redistribuído entre as disponíveis).
      </p>
    </div>
  );
}
