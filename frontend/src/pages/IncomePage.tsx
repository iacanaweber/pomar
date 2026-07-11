import { useEffect, useState } from "react";
import {
  useIncome,
  useIncomeRealized,
  useIncomeSnapshots,
  usePreferences,
  useProjection,
} from "../api/queries";
import type { ProjectionPoint, ProjectionRequest, RealizedMonth } from "../types";
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

const MONTH_SHORT = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

function monthLabel(ym: string): string {
  const m = Number(ym.slice(5, 7));
  return `${MONTH_SHORT[m - 1] ?? ym.slice(5, 7)}/${ym.slice(2, 4)}`;
}

/** Barras mensais dos dividendos RECEBIDOS (Ghostfolio) — a bola de neve de verdade. */
function RealizedBars({ months, currency }: { months: RealizedMonth[]; currency: string }) {
  if (months.length === 0) return null;
  const maxV = Math.max(...months.map((m) => m.total)) || 1;
  return (
    <div className="realized-bars" role="img" aria-label="Dividendos recebidos por mês">
      {months.map((m) => (
        <div key={m.month} className="realized-bar-col" title={`${monthLabel(m.month)}: ${money(m.total, currency)}`}>
          <span className="realized-bar-val">{money(m.total, currency).replace(/ /g, " ")}</span>
          <div className="realized-bar" style={{ height: `${Math.max(4, (m.total / maxV) * 96)}px` }} />
          <span className="realized-bar-label">{monthLabel(m.month)}</span>
        </div>
      ))}
    </div>
  );
}

/** Seção 'Renda recebida': o que de fato caiu na conta, mês a mês (últimos 12m). */
function RealizedSection({ estimatedMonthly, currency }: { estimatedMonthly: number; currency: string }) {
  const realized = useIncomeRealized();
  const data = realized.data;
  if (realized.isLoading) return <p className="muted">Buscando os proventos recebidos…</p>;
  if (!data) return null;
  if ((data.warnings ?? []).length > 0 && (data.months ?? []).length === 0) {
    return (
      <div className="alloc">
        <h3>Renda recebida</h3>
        <p className="muted">{(data.warnings ?? [])[0]}</p>
      </div>
    );
  }
  const months = (data.months ?? []).slice(-12);
  if (months.length === 0) {
    return (
      <div className="alloc">
        <h3>Renda recebida</h3>
        <p className="muted">
          Nenhum dividendo registrado no Ghostfolio ainda. Quando os proventos caírem por lá,
          esta seção mostra a sua renda REAL mês a mês — sem digitar nada aqui.
        </p>
      </div>
    );
  }
  return (
    <div className="alloc">
      <h3>Renda recebida (Ghostfolio)</h3>
      <div className="income-now">
        <div className="income-stat">
          <span className="muted">Últimos 12 meses</span>
          <strong>{money(data.total_12m, currency)}</strong>
        </div>
        <div className="income-stat">
          <span className="muted">Média mensal recebida</span>
          <strong className="income-big">{money(data.monthly_avg_12m, currency)}</strong>
          {estimatedMonthly > 0 && (
            <span className="muted income-gross-note">
              estimada pela carteira atual: {money(estimatedMonthly, currency)}
            </span>
          )}
        </div>
        {(data.last_payments ?? []).length > 0 && (
          <div className="income-stat">
            <span className="muted">Último provento</span>
            <strong>
              {(data.last_payments ?? [])[0].ticker} {money((data.last_payments ?? [])[0].value, currency)}
            </strong>
            <span className="muted income-gross-note">{(data.last_payments ?? [])[0].date}</span>
          </div>
        )}
      </div>
      <RealizedBars months={months} currency={currency} />
      {(data.by_asset_12m ?? []).length > 0 && (
        <p className="muted" style={{ fontSize: 12 }}>
          Quem mais pagou (12m):{" "}
          {(data.by_asset_12m ?? []).slice(0, 5).map((a, i) => (
            <span key={a.ticker}>
              {i > 0 ? " · " : ""}
              <AssetLink ticker={a.ticker} /> {money(a.total, currency)}
            </span>
          ))}
        </p>
      )}
    </div>
  );
}

/** Seção 'Bola de neve real': a série mensal registrada (snapshots) vs o presente. */
function SnapshotsSection({ currency }: { currency: string }) {
  const snaps = useIncomeSnapshots();
  const months = snaps.data?.months ?? [];
  if (months.length < 2) return null; // precisa de história para ser um gráfico honesto
  const w = 520;
  const h = 140;
  const pad = 4;
  const vals = months.map((m) => m.monthly_income ?? 0);
  const maxV = Math.max(...vals) || 1;
  const x = (i: number) => pad + (i / (months.length - 1)) * (w - 2 * pad);
  const y = (v: number) => h - pad - (v / maxV) * (h - 2 * pad);
  const line = vals.map((v, i) => `${x(i)},${y(v)}`).join(" ");
  const first = months[0];
  const last = months[months.length - 1];
  return (
    <div className="alloc">
      <h3>Sua bola de neve real</h3>
      <p className="muted" style={{ marginTop: 0 }}>
        Renda mensal estimada registrada a cada mês — de {money(first.monthly_income ?? 0, currency)} em{" "}
        {monthLabel(first.month)} para <strong>{money(last.monthly_income ?? 0, currency)}</strong> em{" "}
        {monthLabel(last.month)}.
      </p>
      <svg viewBox={`0 0 ${w} ${h}`} className="snowball-svg" role="img" aria-label="Renda mensal registrada por mês">
        <polyline points={line} fill="none" stroke="var(--green)" strokeWidth="2.5" />
      </svg>
    </div>
  );
}

/** Chips 'e se eu aportar +R$X/mês' — o delta que convence a acelerar a bola. */
function WhatIfChips({
  base,
  extra,
  years,
  currency,
}: {
  base: ProjectionRequest;
  extra: number;
  years: number;
  currency: string;
}) {
  const alt = useProjection({ ...base, monthly_contribution: base.monthly_contribution + extra });
  const cur = useProjection(base);
  if (!alt.data || !cur.data) return null;
  const altIncome = alt.data.final_monthly_income_real ?? alt.data.final_monthly_income;
  const curIncome = cur.data.final_monthly_income_real ?? cur.data.final_monthly_income;
  const delta = altIncome - curIncome;
  if (!(delta > 0)) return null;
  return (
    <span className="whatif-chip">
      +{money(extra, currency)}/mês → renda final +{money(delta, currency)} em {years} anos
    </span>
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
  const [inflPct, setInflPct] = useState(4);
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
  const inflOk = inflPct >= 0 && inflPct <= 20;
  const yearsOk = years >= 1 && years <= 60;

  const rawParams = {
    current_value: data?.total_value ?? 0,
    monthly_contribution: parseBRL(aporte) || 0,
    annual_yield: clamp(dyPct, 0, 30) / 100,
    annual_growth: clamp(growthPct, -10, 30) / 100,
    annual_inflation: clamp(inflPct, 0, 20) / 100,
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
            <span className="muted">Renda mensal estimada (líquida)</span>
            <strong className="income-big">{money(data.monthly_income, data.currency)}</strong>
            {data.monthly_income_gross != null && data.monthly_income_gross > data.monthly_income && (
              <span className="muted income-gross-note">
                bruta: {money(data.monthly_income_gross, data.currency)} — o IR de 15% do JCP já foi descontado
              </span>
            )}
          </div>
          <div className="income-stat">
            <span className="muted">Renda anual (líquida)</span>
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

      <RealizedSection
        estimatedMonthly={data?.monthly_income ?? 0}
        currency={data?.currency ?? "BRL"}
      />
      <SnapshotsSection currency={data?.currency ?? "BRL"} />

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
            <span>Inflação esperada (% a.a.)</span>
            <input
              type="number"
              min={0}
              max={20}
              value={inflPct}
              onChange={(e) => setInflPct(Number(e.target.value))}
            />
            {!inflOk && <span className="field-error">Use um valor entre 0% e 20%.</span>}
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

        {proj.isError && (
          <div className="banner banner-warn">
            Não consegui calcular a projeção com essas premissas
            {proj.error instanceof Error && proj.error.message ? ` (${proj.error.message})` : ""}.
            Ajuste os valores e tente de novo.
          </div>
        )}

        {proj.data && (
          <>
            <SnowballChart series={proj.data.series ?? []} />
            <div className="income-now">
              <div className="income-stat">
                <span className="muted">Patrimônio em {clamp(years, 1, 60)} anos</span>
                <strong>{money(proj.data.final_value)}</strong>
              </div>
              <div className="income-stat">
                <span className="muted">
                  Renda mensal projetada{inflPct > 0 ? " (em reais de hoje)" : ""}
                </span>
                <strong className="income-big">
                  {money(
                    inflPct > 0 && proj.data.final_monthly_income_real != null
                      ? proj.data.final_monthly_income_real
                      : proj.data.final_monthly_income,
                  )}
                </strong>
                {inflPct > 0 && proj.data.final_monthly_income_real != null && (
                  <span className="muted income-gross-note">
                    nominal em {clamp(years, 1, 60)} anos: {money(proj.data.final_monthly_income)}
                  </span>
                )}
              </div>
              <div className="income-stat">
                <span className="muted">Total aportado</span>
                <strong>{money(proj.data.total_invested)}</strong>
              </div>
            </div>
            <div className="whatif-row">
              <span className="muted" style={{ fontSize: 12 }}>E se aportar mais?</span>
              {[100, 500, 1000].map((extra) => (
                <WhatIfChips
                  key={extra}
                  base={params}
                  extra={extra}
                  years={clamp(years, 1, 60)}
                  currency="BRL"
                />
              ))}
            </div>
          </>
        )}

        <label className="field" style={{ marginTop: 12 }}>
          <span>Meta de renda mensal (R$) — calcula o aporte necessário</span>
          <input inputMode="decimal" placeholder="ex.: 5000" value={meta} onChange={(e) => setMeta(e.target.value)} />
        </label>
        {proj.data?.required_monthly_contribution != null && parseBRL(meta) > 0 && (
          <p className="strategy-desc">
            Para <strong>{money(parseBRL(meta))}/mês</strong>
            {inflPct > 0 ? " (em reais de hoje)" : ""} em {clamp(years, 1, 60)} anos, aporte{" "}
            <strong>{money(proj.data.required_monthly_contribution)}/mês</strong> (DY {clamp(dyPct, 0, 30)}%, crescimento{" "}
            {clamp(growthPct, -10, 30)}% a.a.{inflPct > 0 ? `, inflação ${clamp(inflPct, 0, 20)}% a.a.` : ""}).
          </p>
        )}
        {proj.data != null && proj.data.required_monthly_contribution == null && parseBRL(meta) > 0 && (
          <p className="strategy-desc">
            Com essas premissas, <strong>nenhum aporte alcança {money(parseBRL(meta))}/mês</strong> no
            horizonte — aumente o DY, o prazo ou revise a meta.
          </p>
        )}
      </div>

      <p className="disclaimer">
        Projeção educativa sob premissas que você define — não é promessa de retorno.
      </p>
    </main>
  );
}
