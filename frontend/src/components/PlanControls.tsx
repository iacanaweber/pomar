import { useState } from "react";
import type { StrategiesResponse } from "../types";
import { Tooltip } from "./Tooltip";

interface Props {
  strategies: StrategiesResponse | null;
  loading: boolean;
  onSubmit: (aporte: number, strategy: string) => void;
}

export function PlanControls({ strategies, loading, onSubmit }: Props) {
  const [aporte, setAporte] = useState("");
  const [strategy, setStrategy] = useState("equilibrado");
  const presets = strategies?.presets ?? {};
  const weights = presets[strategy]?.weights;

  return (
    <form
      className="controls"
      onSubmit={(e) => {
        e.preventDefault();
        const v = parseFloat(aporte.replace(",", "."));
        if (v > 0) onSubmit(v, strategy);
      }}
    >
      <label className="field">
        <span>Quanto você tem para investir hoje?</span>
        <div className="money">
          <span>R$</span>
          <input
            inputMode="decimal"
            placeholder="2000"
            value={aporte}
            onChange={(e) => setAporte(e.target.value)}
            autoFocus
          />
        </div>
      </label>

      <label className="field">
        <Tooltip metricKey="strategy">
          <span>Estratégia</span>
        </Tooltip>
        <select value={strategy} onChange={(e) => setStrategy(e.target.value)}>
          {Object.entries(presets).map(([key, p]) => (
            <option key={key} value={key}>
              {p.label}
            </option>
          ))}
        </select>
      </label>

      {presets[strategy] && (
        <p className="strategy-desc">{presets[strategy].description}</p>
      )}
      {weights && (
        <div className="weights">
          {Object.entries(weights).map(([k, w]) => (
            <Tooltip key={k} metricKey={famKey(k)}>
              <span className="weight-chip">
                {famLabel(k)} {Math.round(w * 100)}%
              </span>
            </Tooltip>
          ))}
        </div>
      )}

      <button className="primary" type="submit" disabled={loading}>
        {loading ? "Analisando o pomar…" : "🌳 Ver recomendações"}
      </button>
    </form>
  );
}

const FAM_LABEL: Record<string, string> = {
  valuation: "Desconto",
  dividend: "Dividendos",
  rebalance: "Rebalanceamento",
  sector: "Setor perene",
};
const FAM_KEY: Record<string, string> = {
  valuation: "graham",
  dividend: "div_yield",
  rebalance: "rebalance_gap",
  sector: "sector_besst",
};
const famLabel = (k: string) => FAM_LABEL[k] ?? k;
const famKey = (k: string) => FAM_KEY[k] ?? "composite_score";
