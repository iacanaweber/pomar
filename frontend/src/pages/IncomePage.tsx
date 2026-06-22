import { useEffect, useState } from "react";
import { useIncome, useProjection } from "../api/queries";
import type { ProjectionPoint } from "../types";
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

export function IncomePage() {
  const income = useIncome();
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

  const proj = useProjection({
    current_value: data?.total_value ?? 0,
    monthly_contribution: parseBRL(aporte) || 0,
    annual_yield: dyPct / 100,
    annual_growth: growthPct / 100,
    years,
    reinvest,
    target_monthly_income: parseBRL(meta) || null,
  });

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
            <span className="muted">Yield da carteira</span>
            <strong>{pct(data.portfolio_yield)}</strong>
          </div>
        </div>
      )}

      {data && (data.by_asset ?? []).length > 0 && (
        <div className="alloc">
          <h3>Quem paga a sua renda</h3>
          <ul className="pf-drill-list">
            {(data.by_asset ?? []).slice(0, 8).map((a) => (
              <li key={a.ticker} className="pf-drill-item">
                <span className="pf-drill-ticker">{a.ticker}</span>
                <span className="pf-drill-name">DY {pct(a.dividend_yield)}</span>
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
              value={dyPct}
              onChange={(e) => {
                setDyTouched(true);
                setDyPct(Number(e.target.value));
              }}
            />
          </label>
          <label className="field">
            <span>Crescimento dos proventos (% a.a.)</span>
            <input type="number" value={growthPct} onChange={(e) => setGrowthPct(Number(e.target.value))} />
          </label>
          <label className="field">
            <span>Anos</span>
            <input type="number" min={1} max={60} value={years} onChange={(e) => setYears(Number(e.target.value))} />
          </label>
          <label className="field" style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
            <input type="checkbox" checked={reinvest} onChange={(e) => setReinvest(e.target.checked)} />
            <span>Reinvestir dividendos</span>
          </label>
        </div>

        {proj.data && (
          <>
            <SnowballChart series={proj.data.series ?? []} />
            <div className="income-now">
              <div className="income-stat">
                <span className="muted">Patrimônio em {years} anos</span>
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
            Para <strong>{money(parseBRL(meta))}/mês</strong> em {years} anos, aporte{" "}
            <strong>{money(proj.data.required_monthly_contribution)}/mês</strong> (DY {dyPct}%, crescimento{" "}
            {growthPct}% a.a.).
          </p>
        )}
      </div>

      <p className="disclaimer">
        Projeção educativa sob premissas que você define — não é promessa de retorno.
      </p>
    </main>
  );
}
