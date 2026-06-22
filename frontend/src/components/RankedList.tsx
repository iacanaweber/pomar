import { useState } from "react";
import type { PlanResponse, ScoredAsset } from "../types";
import { money } from "../lib/format";
import { ScoreBreakdown } from "./ScoreBreakdown";
import { Tooltip } from "./Tooltip";

const RISK_CLASS: Record<string, string> = {
  verde: "risk-verde",
  amarelo: "risk-amarelo",
  vermelho: "risk-vermelho",
};

function AssetCard({ asset }: { asset: ScoredAsset }) {
  const [open, setOpen] = useState(false);
  const score = Math.round(asset.composite_score * 100);
  const reasons = asset.reasons ?? [];
  const redFlags = asset.red_flags ?? [];
  const riskClass = RISK_CLASS[asset.risk_level ?? "verde"] ?? "";
  return (
    <li className="card">
      <button className="card-head" onClick={() => setOpen((v) => !v)}>
        <span className="card-rank">{asset.rank}</span>
        <span className="card-id">
          <span className="card-ticker">{asset.ticker}</span>
          <span className="card-name">{asset.name ?? asset.sector ?? asset.asset_class}</span>
        </span>
        <span className="card-score">
          <Tooltip metricKey="composite_score">
            <span className={`score-badge ${riskClass}`}>{score}</span>
          </Tooltip>
        </span>
        {asset.suggested && (
          <span className="card-buy">
            <Tooltip metricKey="suggested_amount">
              <strong>{money(asset.suggested.invested_exact)}</strong>
            </Tooltip>
            <span className="card-shares">
              {asset.suggested.shares} × {asset.suggested.price ? money(asset.suggested.price) : "—"}
            </span>
          </span>
        )}
        <span className="card-toggle">{open ? "▲" : "▼"}</span>
      </button>

      {reasons.length > 0 && (
        <ul className="card-reasons">
          {reasons.map((r, i) => (
            <li key={i}>🌱 {r}</li>
          ))}
        </ul>
      )}

      {redFlags.length > 0 && (
        <ul className="card-flags">
          {redFlags.map((f, i) => (
            <li key={i}>▲ {f}</li>
          ))}
        </ul>
      )}

      {open && <ScoreBreakdown asset={asset} />}
    </li>
  );
}

export function RankedList({ plan }: { plan: PlanResponse }) {
  const ranking = plan.ranking ?? [];
  const unallocated = plan.unallocated ?? 0;
  const buys = ranking.filter((a) => a.suggested);
  const rest = ranking.filter((a) => !a.suggested);
  return (
    <div className="ranked">
      {buys.length > 0 && (
        <>
          <h2>
            Compras sugeridas para {money(plan.aporte)}
            {unallocated > 0 && <span className="muted"> · sobra {money(unallocated)}</span>}
          </h2>
          <ul className="cards">
            {buys.map((a) => (
              <AssetCard key={a.ticker} asset={a} />
            ))}
          </ul>
        </>
      )}
      {rest.length > 0 && (
        <>
          <h3 className="muted">Outros candidatos no ranking</h3>
          <ul className="cards">
            {rest.map((a) => (
              <AssetCard key={a.ticker} asset={a} />
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
