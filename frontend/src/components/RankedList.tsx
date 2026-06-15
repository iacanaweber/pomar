import { useState } from "react";
import type { PlanResponse, ScoredAsset } from "../types";
import { ScoreBreakdown } from "./ScoreBreakdown";
import { Tooltip } from "./Tooltip";

const brl = (v: number) =>
  v.toLocaleString("pt-br", { style: "currency", currency: "BRL" });

function AssetCard({ asset }: { asset: ScoredAsset }) {
  const [open, setOpen] = useState(false);
  const score = Math.round(asset.composite_score * 100);
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
            <span className="score-badge">{score}</span>
          </Tooltip>
        </span>
        {asset.suggested && (
          <span className="card-buy">
            <Tooltip metricKey="suggested_amount">
              <strong>{brl(asset.suggested.invested_exact)}</strong>
            </Tooltip>
            <span className="card-shares">
              {asset.suggested.shares} × {asset.suggested.price ? brl(asset.suggested.price) : "—"}
            </span>
          </span>
        )}
        <span className="card-toggle">{open ? "▲" : "▼"}</span>
      </button>

      {asset.reasons.length > 0 && (
        <ul className="card-reasons">
          {asset.reasons.map((r, i) => (
            <li key={i}>🌱 {r}</li>
          ))}
        </ul>
      )}

      {open && <ScoreBreakdown asset={asset} />}
    </li>
  );
}

export function RankedList({ plan }: { plan: PlanResponse }) {
  const buys = plan.ranking.filter((a) => a.suggested);
  const rest = plan.ranking.filter((a) => !a.suggested);
  return (
    <div className="ranked">
      {buys.length > 0 && (
        <>
          <h2>
            Compras sugeridas para {brl(plan.aporte)}
            {plan.unallocated > 0 && (
              <span className="muted"> · sobra {brl(plan.unallocated)}</span>
            )}
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
