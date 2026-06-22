import { useEffect, useState, type FormEvent } from "react";
import type { PlanRequest, Preferences, StrategiesResponse } from "../types";
import { useSavePreferences } from "../api/queries";
import { parseBRL } from "../lib/format";
import { Tooltip } from "./Tooltip";

interface Props {
  strategies: StrategiesResponse | null;
  preferences?: Preferences;
  loading: boolean;
  onSubmit: (req: PlanRequest) => void;
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

export function PlanControls({ strategies, preferences, loading, onSubmit }: Props) {
  const [aporte, setAporte] = useState("");
  const [strategy, setStrategy] = useState("equilibrado");
  const [touched, setTouched] = useState(false);
  const [advanced, setAdvanced] = useState(false);

  // Parâmetros do motor (antes inacessíveis na UI).
  const [maxAssets, setMaxAssets] = useState(5);
  const [maxWeightPct, setMaxWeightPct] = useState(20);
  const [minTicket, setMinTicket] = useState("100");
  // Alvos por classe em % (0..100) para edição; convertidos para fração no submit.
  const [targetsPct, setTargetsPct] = useState<Record<string, number>>({});

  const savePrefs = useSavePreferences();

  // Sincroniza o formulário com as preferências salvas quando elas chegam (uma vez).
  useEffect(() => {
    if (!preferences) return;
    setStrategy(preferences.strategy);
    setMaxAssets(preferences.max_assets);
    setMaxWeightPct(Math.round(preferences.max_weight_per_asset * 100));
    setMinTicket(String(preferences.min_ticket));
    setTargetsPct(
      Object.fromEntries(
        Object.entries(preferences.targets).map(([k, v]) => [k, Math.round(v * 100)]),
      ),
    );
    if (preferences.aporte_default) setAporte(String(preferences.aporte_default));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preferences]);

  const presets = strategies?.presets ?? {};
  const hasPresets = Object.keys(presets).length > 0;
  const weights = presets[strategy]?.weights;
  const targetSum = Object.values(targetsPct).reduce((s, v) => s + (v || 0), 0);

  const buildRequest = (): PlanRequest | null => {
    const value = parseBRL(aporte);
    if (!(value > 0)) return null;
    const targets =
      Object.keys(targetsPct).length > 0
        ? Object.fromEntries(Object.entries(targetsPct).map(([k, v]) => [k, (v || 0) / 100]))
        : undefined;
    return {
      aporte: value,
      strategy,
      max_assets: maxAssets,
      max_weight_per_asset: maxWeightPct / 100,
      min_ticket: parseBRL(minTicket) || 0,
      ...(targets ? { targets } : {}),
    };
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setTouched(true);
    const req = buildRequest();
    if (req) onSubmit(req);
  };

  const savePreferences = () => {
    savePrefs.mutate({
      strategy,
      max_assets: maxAssets,
      max_weight_per_asset: maxWeightPct / 100,
      min_ticket: parseBRL(minTicket) || 0,
      ...(Object.keys(targetsPct).length
        ? { targets: Object.fromEntries(Object.entries(targetsPct).map(([k, v]) => [k, (v || 0) / 100])) }
        : {}),
    });
  };

  const valueInvalid = touched && !(parseBRL(aporte) > 0);

  return (
    <form className="controls" onSubmit={submit}>
      <label className="field">
        <span>Quanto você tem para investir hoje?</span>
        <div className={`money ${valueInvalid ? "money-invalid" : ""}`}>
          <span>R$</span>
          <input
            inputMode="decimal"
            placeholder="2000"
            value={aporte}
            onChange={(e) => setAporte(e.target.value)}
            autoFocus
          />
        </div>
        {valueInvalid && <span className="field-error">Informe um valor maior que zero.</span>}
      </label>

      <label className="field">
        <Tooltip metricKey="strategy">
          <span>Estratégia</span>
        </Tooltip>
        <select value={strategy} onChange={(e) => setStrategy(e.target.value)}>
          {hasPresets ? (
            Object.entries(presets).map(([key, p]) => (
              <option key={key} value={key}>
                {p.label}
              </option>
            ))
          ) : (
            <option value="equilibrado">Carregando estratégias…</option>
          )}
        </select>
      </label>

      {presets[strategy] && <p className="strategy-desc">{presets[strategy].description}</p>}
      {weights && (
        <div className="weights">
          {Object.entries(weights).map(([k, w]) => (
            <Tooltip key={k} metricKey={FAM_KEY[k] ?? "composite_score"}>
              <span className="weight-chip">
                {FAM_LABEL[k] ?? k} {Math.round(w * 100)}%
              </span>
            </Tooltip>
          ))}
        </div>
      )}

      <button type="button" className="link-button" onClick={() => setAdvanced((v) => !v)}>
        {advanced ? "▲ Ocultar ajustes avançados" : "▼ Ajustes avançados"}
      </button>

      {advanced && (
        <div className="advanced">
          <div className="adv-row">
            <label className="field">
              <span>Máx. de ativos</span>
              <input
                type="number"
                min={1}
                max={20}
                value={maxAssets}
                onChange={(e) => setMaxAssets(Number(e.target.value))}
              />
            </label>
            <label className="field">
              <Tooltip metricKey="weight_position">
                <span>Teto por ativo (%)</span>
              </Tooltip>
              <input
                type="number"
                min={1}
                max={100}
                value={maxWeightPct}
                onChange={(e) => setMaxWeightPct(Number(e.target.value))}
              />
            </label>
            <label className="field">
              <Tooltip metricKey="suggested_amount">
                <span>Ticket mínimo (R$)</span>
              </Tooltip>
              <input
                inputMode="decimal"
                value={minTicket}
                onChange={(e) => setMinTicket(e.target.value)}
              />
            </label>
          </div>

          {Object.keys(targetsPct).length > 0 && (
            <div className="targets-editor">
              <Tooltip metricKey="rebalance_gap">
                <span className="targets-title">Metas por classe (%)</span>
              </Tooltip>
              <div className="adv-row">
                {Object.entries(targetsPct).map(([cls, v]) => (
                  <label className="field" key={cls}>
                    <span>{cls}</span>
                    <input
                      type="number"
                      min={0}
                      max={100}
                      value={v}
                      onChange={(e) =>
                        setTargetsPct((t) => ({ ...t, [cls]: Number(e.target.value) }))
                      }
                    />
                  </label>
                ))}
              </div>
              <span className={`targets-sum ${Math.abs(targetSum - 100) > 0.5 ? "warn" : ""}`}>
                soma: {targetSum}% {Math.abs(targetSum - 100) > 0.5 ? "(deveria ser 100%)" : "✓"}
              </span>
            </div>
          )}

          <button
            type="button"
            className="link-button"
            onClick={savePreferences}
            disabled={savePrefs.isPending}
          >
            {savePrefs.isPending ? "Salvando…" : "💾 Salvar como meu padrão"}
          </button>
        </div>
      )}

      <button className="primary" type="submit" disabled={loading}>
        {loading ? "Analisando o pomar…" : "🌳 Ver recomendações"}
      </button>
    </form>
  );
}
