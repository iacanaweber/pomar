import { useEffect, useState } from "react";
import { useIncome, usePreferences, useProjection } from "../api/queries";
import type { ProjectionPoint } from "../types";
import { AssetLink } from "../components/AssetLink";
import { GoalProgress } from "../components/GoalProgress";
import { Tooltip } from "../components/Tooltip";
import { useDebouncedValue } from "../hooks/useDebouncedValue";
import { money, parseBRL, pct } from "../lib/format";

/** Gráfico de área simples (SVG) do patrimônio projetado por ano. */
function SnowballChart({ series }: { series: ProjectionPoint[] }) {
  if (series.length < 2) return null;
  const w = 520;
  const h = 160;
  const pad = 4;
  const maxV = Math.max(...series.map((p) => p.value)) || 1;
  const x = (i: number) => pad + (i / (series.length - 1)) * (w - 2 * pad);
  const y = (v: number) => h - pad - (v / maxV) * (h - 2 * pad);
  const line = series.map((p, i) => `${x(i)},${y(p.value)}`).join(" ");
  const area = `${pad},${h - pad} ${line} ${w - pad},${h - pad}`;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="snowball-svg" role="img" aria-label="Projeção do patrimônio por ano">
      <polygon points={area} fill="var(--leaf)" opacity="0.18" />
      <polyline points={line} fill="none" stroke="var(--green)" strokeWidth="2.5" />
    </svg>
  );
}

const clamp = (v: number, min: number, max: number) => Math.min(Math.max(v, min), max);

export function IncomePage() {
  const income = useIncome();
  const prefs = usePreferences();
  const data = income.data;

  const [aporte, setAporte] = useState("1000");
  const [dyPct, setDyPct] = useState(6);
  const [dyTouched, setDyTouched] = useState(false);
  const [growthPct, setGrowthPct] = useState(5);
  const [years, setYears] = useState(20);
  const [reinvest, setReinvest] = useState(true);
  const [meta, setMeta] = useState("");

  // semeia o DY com o yield atual da carteira quando ele chega (se o usuário não mexeu)
  useEffect(() => {
    if (!dyTouched && data && data.portfolio_yield > 0) {
      setDyPct(Math.round(data.portfolio_yield * 1000) / 10);
    }
  }, [data, dyTouched]);

  // semeia crescimento/horizonte das preferências persistidas (uma vez)
  useEffect(() => {
    if (!prefs.data) return;
    if (prefs.data.annual_growth != null) setGrowthPct(Math.round(prefs.data.annual_growth * 1000) / 10);
    if (prefs.data.target_horizon_years != null) setYears(prefs.data.target_horizon_years);
  }, [prefs.data]);

  // valida e clampa os inputs antes de mandar pra projeção (e mostra erro inline)
  const dyOk = dyPct >= 0 && dyPct <= 30;
  const growthOk = growthPct >= -10 && growthPct <= 30;
  const yearsOk = years >= 1 && years <= 60;

  const rawParams = {
    current_value: data?.total_value ?? 0,
    monthly_contribution: parseBRL(aporte) || 0,
    annual_yield: clamp(dyPct, 0, 30) / 100,
    annual_growth: clamp(growthPct, -10, 30) / 100,
    years: clamp(years, 1, 60),
    reinvest,
    target_monthly_income: parseBRL(meta) || null,
  };
  // debounce: evita uma rajada de requests a cada tecla
  const params = useDebouncedValue(rawParams, 350);
  const proj = useProjection(params);
  const recalculating = proj.isFetching && proj.data != null;

  return (
    <main className="page">
      <h2>Renda passiva</h2>

      {income.isLoading && <p className="muted">Calculando a renda da carteira…</p>}
      {(data?.warnings ?? []).length > 0 && (
        <div className="banner banner-warn">
          {(data?.warnings ?? []).map((w, i) => (
            <div key={i}>• {w}</div>
          ))}
        </div>
      )}

      <GoalProgress />

      {data && (
        <div className="income-now">
          <div className="income-stat">
            <span className="muted">Renda mensal estimada</span>
            <strong className="income-big">{money(data.monthly_income, data.currency)}</strong>
          </div>
          <div className="income-stat">
            <span className="muted">Renda anual</span>
            <strong>{money(data.annual_income, data.currency)}</strong>
          </div>
          <div className="income-stat">
            <Tooltip metricKey="div_yield">
              <span className="muted">Yield da carteira</span>
            </Tooltip>
            <strong>{pct(data.portfolio_yield)}</strong>
          </div>
          {data.yield_on_cost != null && (
            <div className="income-stat">
              <Tooltip metricKey="yield_on_cost">
                <span className="muted">Yield on Cost</span>
              </Tooltip>
              <strong>{pct(data.yield_on_cost)}</strong>
            </div>
          )}
        </div>
      )}

      {data && (data.by_asset ?? []).length > 0 && (
        <div className="alloc">
          <h3>Quem paga a sua renda</h3>
          <ul className="pf-drill-list">
            {(data.by_asset ?? []).slice(0, 8).map((a) => (
              <li key={a.ticker} className="pf-drill-item income-asset-row">
                <span className="pf-drill-ticker"><AssetLink ticker={a.ticker} /></span>
                <span className="income-asset-yields">
                  DY {pct(a.dividend_yield)}
                  {a.yield_on_cost != null && (
                    <Tooltip metricKey="yield_on_cost">
                      <span className="yoc-tag">
                        · YoC {pct(a.yield_on_cost)}
                        {a.yield_on_cost > a.dividend_yield ? " ↑" : ""}
                      </span>
                    </Tooltip>
                  )}
                </span>
                <span className="pf-drill-val">{money(a.annual_income, data.currency)}/ano</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="alloc">
        <h3>Bola de neve de dividendos</h3>
        <p className="muted" style={{ marginTop: 0 }}>
          Simule reinvestindo os proventos e aportando todo mês. Premissas editáveis:
        </p>
        <div className="adv-row">
          <label className="field">
            <span>Aporte mensal (R$)</span>
            <input inputMode="decimal" value={aporte} onChange={(e) => setAporte(e.target.value)} />
          </label>
          <label className="field">
            <span>DY anual (%)</span>
            <input
              type="number"
              min={0}
              max={30}
              value={dyPct}
              onChange={(e) => {
                setDyTouched(true);
                setDyPct(Number(e.target.value));
              }}
            />
            {!dyOk && <span className="field-error">Use um valor entre 0% e 30%.</span>}
          </label>
          <label className="field">
            <span>Crescimento dos proventos (% a.a.)</span>
            <input
              type="number"
              min={-10}
              max={30}
              value={growthPct}
              onChange={(e) => setGrowthPct(Number(e.target.value))}
            />
            {!growthOk && <span className="field-error">Use um valor entre −10% e 30%.</span>}
          </label>
          <label className="field">
            <span>Anos</span>
            <input type="number" min={1} max={60} value={years} onChange={(e) => setYears(Number(e.target.value))} />
            {!yearsOk && <span className="field-error">Use entre 1 e 60 anos.</span>}
          </label>
          <label className="field" style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
            <input type="checkbox" checked={reinvest} onChange={(e) => setReinvest(e.target.checked)} />
            <span>Reinvestir dividendos</span>
          </label>
        </div>

        {recalculating && <p className="muted" style={{ fontSize: 12 }}>atualizando…</p>}

        {proj.data && (
          <>
            <SnowballChart series={proj.data.series ?? []} />
            <div className="income-now">
              <div className="income-stat">
                <span className="muted">Patrimônio em {clamp(years, 1, 60)} anos</span>
                <strong>{money(proj.data.final_value)}</strong>
              </div>
              <div className="income-stat">
                <span className="muted">Renda mensal projetada</span>
                <strong className="income-big">{money(proj.data.final_monthly_income)}</strong>
              </div>
              <div className="income-stat">
                <span className="muted">Total aportado</span>
                <strong>{money(proj.data.total_invested)}</strong>
              </div>
            </div>
          </>
        )}

        <label className="field" style={{ marginTop: 12 }}>
          <span>Meta de renda mensal (R$) — calcula o aporte necessário</span>
          <input inputMode="decimal" placeholder="ex.: 5000" value={meta} onChange={(e) => setMeta(e.target.value)} />
        </label>
        {proj.data?.required_monthly_contribution != null && parseBRL(meta) > 0 && (
          <p className="strategy-desc">
            Para <strong>{money(parseBRL(meta))}/mês</strong> em {clamp(years, 1, 60)} anos, aporte{" "}
            <strong>{money(proj.data.required_monthly_contribution)}/mês</strong> (DY {clamp(dyPct, 0, 30)}%, crescimento{" "}
            {clamp(growthPct, -10, 30)}% a.a.).
          </p>
        )}
      </div>

      <p className="disclaimer">
        Projeção educativa sob premissas que você define — não é promessa de retorno.
      </p>
    </main>
  );
}
