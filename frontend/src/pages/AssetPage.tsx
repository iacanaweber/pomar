import { useNavigate, useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { useAsset } from "../api/queries";
import { CeilingBadge } from "../components/CeilingBadge";
import { ScoreBreakdown } from "../components/ScoreBreakdown";
import { Tooltip } from "../components/Tooltip";
import type { Fundamentals } from "../types";
import { money, pct } from "../lib/format";

const RISK_CLASS: Record<string, string> = {
  verde: "risk-verde",
  amarelo: "risk-amarelo",
  vermelho: "risk-vermelho",
};

function Fund({ label, value }: { label: string; value: string | null }) {
  if (value == null) return null;
  return (
    <div className="fund-item">
      <span className="muted">{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export function AssetPage() {
  const { ticker = "" } = useParams();
  const navigate = useNavigate();
  const { data, isLoading, error } = useAsset(ticker);

  if (isLoading)
    return (
      <main className="page">
        <p className="muted">Carregando {ticker}…</p>
      </main>
    );
  if (error || !data)
    return (
      <main className="page">
        <button className="link-button" onClick={() => navigate(-1)}>
          ← voltar
        </button>
        <div className="banner banner-error">
          {error instanceof ApiError ? error.userMessage : `Não encontrei dados de ${ticker}.`}
        </div>
      </main>
    );

  const { asset, scored } = data;
  const f = (asset.fundamentals ?? {}) as Fundamentals;
  const score = Math.round((scored.composite_score ?? 0) * 100);
  const riskClass = RISK_CLASS[scored.risk_level ?? "verde"] ?? "";
  const years = Object.entries(asset.dividends_by_year ?? {}).sort(([a], [b]) => a.localeCompare(b));
  const maxDiv = Math.max(1, ...years.map(([, v]) => v));

  return (
    <main className="page">
      <button className="link-button" onClick={() => navigate(-1)}>
        ← voltar
      </button>

      <div className="asset-head">
        <div>
          <h2 style={{ margin: 0 }}>{asset.ticker}</h2>
          <p className="muted" style={{ margin: 0 }}>
            {asset.name ?? asset.sector ?? asset.asset_class} · {asset.asset_class}
            {asset.sector ? ` · ${asset.sector}` : ""}
          </p>
        </div>
        <div className="asset-head-right">
          {asset.price != null && <strong className="asset-price">{money(asset.price)}</strong>}
          <span className={`score-badge ${riskClass}`}>{score}</span>
        </div>
      </div>

      {asset.stale && <div className="banner banner-warn">⏳ Dados de cache (possivelmente defasados).</div>}

      <CeilingBadge
        ceiling={scored.bazin_ceiling_price}
        price={asset.price}
        margin={scored.bazin_margin}
        belowCeiling={scored.bazin_below_ceiling}
        variant="block"
      />

      {(scored.reasons ?? []).length > 0 && (
        <ul className="card-reasons">
          {(scored.reasons ?? []).map((r, i) => (
            <li key={i}>🌱 {r}</li>
          ))}
        </ul>
      )}
      {(scored.red_flags ?? []).length > 0 && (
        <ul className="card-flags">
          {(scored.red_flags ?? []).map((r, i) => (
            <li key={i}>▲ {r}</li>
          ))}
        </ul>
      )}

      <div className="alloc">
        <h3>Fundamentos</h3>
        <div className="fund-grid">
          <Fund label="P/L" value={f.pl != null ? f.pl.toFixed(2) : null} />
          <Fund label="P/VP" value={f.pvp != null ? f.pvp.toFixed(2) : null} />
          {f.dividend_yield != null && (
            <div className="fund-item">
              <Tooltip metricKey="net_yield">
                <span className="muted">Dividend Yield</span>
              </Tooltip>
              <strong>
                {pct(f.dividend_yield)} <span className="muted" style={{ fontWeight: 400 }}>bruto</span>
              </strong>
              {f.dividend_yield_net != null && (
                <span className="muted" style={{ fontSize: 12 }}>
                  {pct(f.dividend_yield_net)} líquido
                </span>
              )}
            </div>
          )}
          <Fund label="LPA" value={f.lpa != null ? f.lpa.toFixed(2) : null} />
          <Fund label="VPA" value={f.vpa != null ? f.vpa.toFixed(2) : null} />
          <Fund label="ROE" value={f.roe != null ? pct(f.roe) : null} />
          <Fund label="Margem líquida" value={f.net_margin != null ? pct(f.net_margin) : null} />
          <Fund label="Dív. líq./EBITDA" value={f.net_debt_to_ebitda != null ? f.net_debt_to_ebitda.toFixed(2) : null} />
          <Fund label="Liquidez corrente" value={f.current_ratio != null ? f.current_ratio.toFixed(2) : null} />
        </div>
        <p className="muted" style={{ fontSize: 12, marginBottom: 0 }}>Fonte: {asset.source}</p>
      </div>

      {years.length > 0 && (
        <div className="alloc">
          <h3>Proventos por ano</h3>
          <div className="prov-bars">
            {years.map(([y, v]) => (
              <div key={y} className="prov-row">
                <span className="prov-year">{y}</span>
                <div className="prov-track">
                  <div className="prov-fill" style={{ width: `${(v / maxDiv) * 100}%` }} />
                </div>
                <span className="prov-val">{money(v)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="alloc">
        <h3>Como o score foi calculado</h3>
        <ScoreBreakdown asset={scored} />
      </div>

      <p className="disclaimer">Conteúdo educativo. Não é recomendação de investimento.</p>
    </main>
  );
}
