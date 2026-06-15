import { useState } from "react";
import type { StrategiesResponse, StrategyPreset } from "../types";
import { Tooltip } from "./Tooltip";

interface Props {
  strategies: StrategiesResponse | null;
  loading: boolean;
  onSubmit: (aporte: number, strategy: string) => void;
}

// Lista embutida: garante que o seletor SEMPRE apareça, mesmo que o fetch ao
// backend falhe ou demore. O backend, quando responde, sobrepõe esta lista.
const FALLBACK_PRESETS: Record<string, StrategyPreset> = {
  equilibrado: {
    label: "Equilibrado",
    description: "Mistura desconto, dividendos, rebalanceamento e setores perenes.",
    weights: { valuation: 0.3, dividend: 0.35, rebalance: 0.2, sector: 0.15 },
  },
  barsi: {
    label: "Barsi (dividendos perenes)",
    description: "Foco em pagadoras consistentes de setores essenciais (BESST), buy & hold.",
    weights: { valuation: 0.2, dividend: 0.4, rebalance: 0.15, sector: 0.25 },
  },
  bazin: {
    label: "Bazin (preço-teto)",
    description: "Comprar com margem sobre o preço-teto (DY-alvo de 6%) e dividendos recorrentes.",
    weights: { valuation: 0.25, dividend: 0.5, rebalance: 0.2, sector: 0.05 },
  },
  graham: {
    label: "Graham (valor)",
    description: "Margem de segurança no preço: P/VP e P/L baixos, P/L×P/VP ≤ 22,5.",
    weights: { valuation: 0.55, dividend: 0.2, rebalance: 0.25, sector: 0.0 },
  },
};

export function PlanControls({ strategies, loading, onSubmit }: Props) {
  const [aporte, setAporte] = useState("");
  const [strategy, setStrategy] = useState("equilibrado");
  const presets =
    strategies?.presets && Object.keys(strategies.presets).length
      ? strategies.presets
      : FALLBACK_PRESETS;
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
