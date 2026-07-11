import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import type { PlanRequest, Preferences, StrategiesResponse } from "../types";
import { useIncomeRealized, useSavePreferences, useWatchlist } from "../api/queries";
import { money, parseBRL } from "../lib/format";
import { SavedToast } from "./SavedToast";
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

export const CLASS_LABEL: Record<string, string> = {
  STOCK: "Ações",
  FII: "FIIs",
  ETF: "ETFs",
  BDR: "BDRs",
};

const FOCUS_OPTIONS: { key: string; label: string }[] = [
  { key: "BALANCE", label: "🌱 Balancear" },
  { key: "STOCK", label: "Ações" },
  { key: "FII", label: "FIIs" },
  { key: "ETF", label: "ETFs" },
  { key: "BDR", label: "BDRs" },
];

/** Editor da carteira alvo de UMA classe (ticker + % somando 100). É uma configuração
 *  estrutural, salva nas preferências na hora — o plano lê do servidor, então edição
 *  não salva não afeta o plano. */
function BasketEditor({ focusClass, preferences }: { focusClass: string; preferences?: Preferences }) {
  const watchlist = useWatchlist();
  const savePrefs = useSavePreferences();
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState<{ ticker: string; pct: number }[]>([]);
  const [newTicker, setNewTicker] = useState("");
  const [savedAt, setSavedAt] = useState<number | null>(null);

  useEffect(() => {
    const saved = preferences?.class_targets?.[focusClass] ?? {};
    setRows(
      Object.entries(saved).map(([t, w]) => ({ ticker: t, pct: Math.round(w * 1000) / 10 })),
    );
  }, [preferences, focusClass]);

  const label = CLASS_LABEL[focusClass] ?? focusClass;
  const saved = preferences?.class_targets?.[focusClass] ?? {};
  const classTickers = (watchlist.data?.items ?? [])
    .filter((i) => i.asset_class === focusClass && i.valid === 1)
    .map((i) => i.ticker)
    .filter((t) => !rows.some((r) => r.ticker === t));
  const sum = rows.reduce((s, r) => s + (r.pct || 0), 0);
  // mesma tolerância do backend (0,1%): fora disso o PUT seria rejeitado com 422
  const sumOk = Math.abs(sum - 100) <= 0.1;

  const addRow = () => {
    const t = newTicker.trim().toUpperCase();
    if (!t || rows.some((r) => r.ticker === t)) return;
    setRows((rs) => [...rs, { ticker: t, pct: 0 }]);
    setNewTicker("");
  };

  const save = () => {
    const basket = Object.fromEntries(
      rows.filter((r) => r.ticker.trim()).map((r) => [r.ticker.trim().toUpperCase(), (r.pct || 0) / 100]),
    );
    savePrefs.mutate(
      { class_targets: { ...(preferences?.class_targets ?? {}), [focusClass]: basket } },
      { onSuccess: () => setSavedAt(Date.now()) },
    );
  };

  return (
    <div className="basket-editor">
      <SavedToast show={savedAt} message="Carteira alvo salva." />
      <button type="button" className="link-button" onClick={() => setOpen((v) => !v)}>
        {open ? "▲" : "▼"} 🎯 Carteira alvo de {label}
        {Object.keys(saved).length > 0 ? ` (ativa: ${Object.keys(saved).length} ativos)` : " (opcional)"}
      </button>
      {open && (
        <div className="targets-editor">
          <span className="muted">
            Defina o peso de cada ativo dentro de {label}: o plano passa a comprar o que
            estiver mais longe desse alvo (em vez do ranking) e ignora quem está fora da lista.
          </span>
          <div className="basket-rows">
            {rows.map((r, idx) => (
              <div className="basket-row" key={r.ticker}>
                <span className="card-ticker">{r.ticker}</span>
                <input
                  type="number"
                  min={0}
                  max={100}
                  step={0.1}
                  value={r.pct}
                  aria-label={`Peso de ${r.ticker} (%)`}
                  onChange={(e) =>
                    setRows((rs) => rs.map((x, i) => (i === idx ? { ...x, pct: Number(e.target.value) } : x)))
                  }
                />
                <span className="muted">%</span>
                <button
                  type="button"
                  className="link-button"
                  aria-label={`Remover ${r.ticker} da carteira alvo`}
                  onClick={() => setRows((rs) => rs.filter((_, i) => i !== idx))}
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
          <div className="basket-add">
            <input
              list={`basket-tickers-${focusClass}`}
              placeholder="Ticker (ex.: BTGL11)"
              value={newTicker}
              aria-label="Ticker para adicionar à carteira alvo"
              onChange={(e) => setNewTicker(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  addRow();
                }
              }}
            />
            <datalist id={`basket-tickers-${focusClass}`}>
              {classTickers.map((t) => (
                <option key={t} value={t} />
              ))}
            </datalist>
            <button type="button" className="link-button" onClick={addRow} disabled={!newTicker.trim()}>
              ＋ adicionar
            </button>
          </div>
          {rows.length > 0 && (
            <span className={`targets-sum ${sumOk ? "" : "warn"}`}>
              soma: {Math.round(sum * 10) / 10}% {sumOk ? "✓" : "(deveria ser 100%)"}
            </span>
          )}
          <button
            type="button"
            className="link-button"
            onClick={save}
            disabled={savePrefs.isPending || (rows.length > 0 && !sumOk)}
          >
            {savePrefs.isPending
              ? "Salvando…"
              : rows.length === 0 && Object.keys(saved).length > 0
                ? "💾 Salvar (remove a carteira alvo)"
                : "💾 Salvar carteira alvo"}
          </button>
        </div>
      )}
    </div>
  );
}

/** Contexto do foco: quem o plano vai considerar (cesta > favoritos > watchlist toda). */
function FocusContext({ focusClass, preferences }: { focusClass: string; preferences?: Preferences }) {
  const watchlist = useWatchlist();
  const basket = preferences?.class_targets?.[focusClass] ?? {};
  const hasBasket = Object.keys(basket).length > 0;
  const favCount = (watchlist.data?.items ?? []).filter(
    (i) => i.asset_class === focusClass && i.favorite === 1 && i.valid === 1,
  ).length;
  const label = CLASS_LABEL[focusClass] ?? focusClass;
  return (
    <div className="focus-context">
      {hasBasket ? (
        <span className="muted">
          🎯 Carteira alvo ativa — o plano compra o que está mais longe do alvo abaixo.
        </span>
      ) : favCount > 0 ? (
        <span className="muted">
          ⭐ Só seus {favCount} favoritos de {label} serão considerados ·{" "}
          <Link to="/watchlist">gerenciar</Link>
        </span>
      ) : (
        <span className="muted">
          Considerando toda a watchlist de {label} ·{" "}
          <Link to="/watchlist">marcar favoritos ⭐</Link>
        </span>
      )}
      <BasketEditor focusClass={focusClass} preferences={preferences} />
    </div>
  );
}

export function PlanControls({ strategies, preferences, loading, onSubmit }: Props) {
  const [aporte, setAporte] = useState("");
  const [strategy, setStrategy] = useState("equilibrado");
  const [touched, setTouched] = useState(false);
  const [advanced, setAdvanced] = useState(false);
  const [focus, setFocus] = useState("BALANCE");
  const [editTargets, setEditTargets] = useState(false);

  // Parâmetros do motor (antes inacessíveis na UI).
  const [maxAssets, setMaxAssets] = useState(5);
  const [maxWeightPct, setMaxWeightPct] = useState(20);
  const [minTicket, setMinTicket] = useState("100");
  const [reserveTargetPct, setReserveTargetPct] = useState(0);
  const [inflationPct, setInflationPct] = useState(4);
  const [includeReserveIncome, setIncludeReserveIncome] = useState(false);
  // Alvos por classe em % (0..100) para edição; convertidos para fração no submit.
  const [targetsPct, setTargetsPct] = useState<Record<string, number>>({});

  const savePrefs = useSavePreferences();
  const [savedAt, setSavedAt] = useState<number | null>(null);

  // Reinvestimento assistido: proventos recebidos nos últimos 30 dias (Ghostfolio)
  // entram no aporte com um toque — o gesto central da bola de neve, sem conta de cabeça.
  const realized = useIncomeRealized();
  const [reinvested, setReinvested] = useState(false);
  const received30d = realized.data?.total_30d ?? 0;
  const addReinvest = () => {
    const current = parseBRL(aporte);
    const base = Number.isFinite(current) ? current : 0;
    setAporte(String(Math.round((base + received30d) * 100) / 100));
    setReinvested(true);
  };

  // Sincroniza o formulário com as preferências salvas quando elas chegam (uma vez).
  useEffect(() => {
    if (!preferences) return;
    setStrategy(preferences.strategy);
    setFocus(preferences.focus || "BALANCE");
    setMaxAssets(preferences.max_assets);
    setMaxWeightPct(Math.round(preferences.max_weight_per_asset * 100));
    setMinTicket(String(preferences.min_ticket));
    setReserveTargetPct(Math.round((preferences.reserve_target ?? 0) * 100));
    setInflationPct(Math.round(((preferences.expected_inflation ?? 0.04) * 1000)) / 10);
    setIncludeReserveIncome(!!preferences.include_reserve_income);
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
      focus,
      max_assets: maxAssets,
      max_weight_per_asset: maxWeightPct / 100,
      min_ticket: parseBRL(minTicket) || 0,
      allow_empty_portfolio: false, // fail-closed: sem carteira, o plano é abortado
      ...(targets ? { targets } : {}),
      ...(reserveTargetPct > 0 ? { reserve_target: reserveTargetPct / 100 } : {}),
    };
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setTouched(true);
    const req = buildRequest();
    if (req) onSubmit(req);
  };

  const savePreferences = () => {
    savePrefs.mutate(
      {
        strategy,
        focus,
        max_assets: maxAssets,
        max_weight_per_asset: maxWeightPct / 100,
        min_ticket: parseBRL(minTicket) || 0,
        reserve_target: reserveTargetPct / 100,
        expected_inflation: inflationPct / 100,
        include_reserve_income: includeReserveIncome,
        ...(parseBRL(aporte) > 0 ? { aporte_default: parseBRL(aporte) } : {}),
        ...(Object.keys(targetsPct).length
          ? { targets: Object.fromEntries(Object.entries(targetsPct).map(([k, v]) => [k, (v || 0) / 100])) }
          : {}),
      },
      { onSuccess: () => setSavedAt(Date.now()) },
    );
  };

  const valueInvalid = touched && !(parseBRL(aporte) > 0);

  return (
    <form className="controls" onSubmit={submit}>
      <SavedToast show={savedAt} />
      {received30d > 0 && !reinvested && (
        <div className="banner reinvest-banner">
          💰 Você recebeu <strong>{money(received30d)}</strong> em proventos nos últimos 30 dias.{" "}
          <button type="button" className="link-button" onClick={addReinvest}>
            somar ao aporte
          </button>
        </div>
      )}
      {reinvested && (
        <p className="muted" style={{ fontSize: 12, margin: "0 0 4px" }}>
          ✓ {money(received30d)} de proventos somados ao aporte — bola de neve girando.
        </p>
      )}
      <div className="seg focus-seg" role="tablist" aria-label="Foco do aporte">
        {FOCUS_OPTIONS.map((o) => (
          <button
            key={o.key}
            type="button"
            role="tab"
            aria-selected={focus === o.key}
            className={`seg-btn ${focus === o.key ? "seg-on" : ""}`}
            onClick={() => setFocus(o.key)}
          >
            {o.label}
          </button>
        ))}
      </div>

      {focus === "BALANCE" && Object.keys(targetsPct).length > 0 && (
        <div className="focus-context">
          <span className="muted">
            Meta da carteira:{" "}
            {Object.entries(targetsPct)
              .map(([cls, v]) => `${v}% ${CLASS_LABEL[cls] ?? cls}`)
              .join(" · ")}{" "}
            <button type="button" className="link-button" onClick={() => setEditTargets((v) => !v)}>
              {editTargets ? "fechar" : "✏️ editar"}
            </button>
          </span>
          {editTargets && (
            <div className="targets-editor">
              <Tooltip metricKey="rebalance_gap">
                <span className="targets-title">Metas por classe (%)</span>
              </Tooltip>
              <div className="adv-row">
                {Object.entries(targetsPct).map(([cls, v]) => (
                  <label className="field" key={cls}>
                    <span>{CLASS_LABEL[cls] ?? cls}</span>
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
              <span className="muted">
                Vale para o próximo plano; use “💾 Salvar como meu padrão” (em ajustes
                avançados) para fixar.
              </span>
            </div>
          )}
        </div>
      )}

      {focus !== "BALANCE" && <FocusContext focusClass={focus} preferences={preferences} />}

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
            <label className="field">
              <Tooltip metricKey="reserve_target">
                <span>Reserva-alvo (%)</span>
              </Tooltip>
              <input
                type="number"
                min={0}
                max={100}
                value={reserveTargetPct}
                onChange={(e) => setReserveTargetPct(Number(e.target.value))}
              />
            </label>
            <label className="field">
              <Tooltip metricKey="income_target">
                <span>Inflação esperada (% a.a.)</span>
              </Tooltip>
              <input
                type="number"
                min={0}
                max={20}
                step={0.5}
                value={inflationPct}
                onChange={(e) => setInflationPct(Number(e.target.value))}
              />
            </label>
          </div>
          <label className="field" style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
            <input
              type="checkbox"
              checked={includeReserveIncome}
              onChange={(e) => setIncludeReserveIncome(e.target.checked)}
            />
            <Tooltip metricKey="fixed_income_yield">
              <span>Contar a renda da reserva na meta de renda</span>
            </Tooltip>
          </label>

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
