import { useCreateOrder } from "../api/queries";
import type { PlanAsset, PlanResponse } from "../types";
import { classLabel } from "../lib/classes";
import { money } from "../lib/format";
import { AssetLink } from "./AssetLink";
import { CeilingBadge } from "./CeilingBadge";
import { Tooltip } from "./Tooltip";
import { Icon } from "./Icon";

const RISK_CLASS: Record<string, string> = {
  verde: "risk-verde",
  amarelo: "risk-amarelo",
  vermelho: "risk-vermelho",
};

const pp = (v: number) => `${(v * 100).toFixed(1).replace(".", ",")}%`;

/** Fecha o ciclo do aporte: comprou na corretora → um toque registra a execução
 *  (pré-preenchida com a sugestão do plano) e alimenta histórico + disciplina. */
function RegisterBuyButton({ asset, planId }: { asset: PlanAsset; planId?: number | null }) {
  const create = useCreateOrder();
  const s = asset.suggested;
  if (!s) return null;
  if (create.isSuccess) return <span className="order-registered">✓ compra registrada</span>;
  return (
    <button
      className="link-button order-register"
      disabled={create.isPending}
      onClick={(e) => {
        e.stopPropagation();
        create.mutate({
          ticker: asset.ticker,
          asset_class: asset.asset_class ?? "STOCK",
          shares: s.shares,
          price: s.price ?? 0,
          fees: 0,
          plan_id: planId ?? null,
          note: "registrado do plano",
        });
      }}
    >
      {create.isPending ? "registrando…" : "Registrei a compra"}
    </button>
  );
}

/** Barra da cesta: onde o ativo está hoje, onde fica depois da compra e onde é o alvo.
 *  Uma linha só responde "por que este valor?" sem abrir nada. */
function BasketBar({ asset }: { asset: PlanAsset }) {
  const target = asset.basket_target_pct;
  const current = asset.basket_current_pct;
  const after = asset.basket_after_pct;
  if (target == null || current == null) return null;
  // escala: o maior dos três com folga, para o marcador de alvo nunca colar na borda
  const max = Math.max(target, current, after ?? 0) * 1.15 || 1;
  const w = (v: number) => `${Math.min(100, (v / max) * 100)}%`;
  const grew = after != null && after > current + 0.0001;
  return (
    <div className="basket-bar-wrap">
      <div className="basket-bar" role="img" aria-label={`peso na cesta: ${pp(current)}, alvo ${pp(target)}`}>
        {grew && <span className="basket-bar-after" style={{ width: w(after) }} />}
        <span className="basket-bar-now" style={{ width: w(current) }} />
        <span className="basket-bar-target" style={{ left: w(target) }} />
      </div>
      <span className="basket-bar-legend muted">
        na cesta de {classLabel(asset.asset_class ?? "")}: {pp(current)}
        {grew ? ` → ${pp(after!)}` : ""} · alvo {pp(target)}
      </span>
    </div>
  );
}

function AssetCard({ asset, planId }: { asset: PlanAsset; planId?: number | null }) {
  const reasons = asset.reasons ?? [];
  const redFlags = asset.red_flags ?? [];
  const riskClass = RISK_CLASS[asset.risk_level ?? "verde"] ?? "";
  // Desconto é ortogonal ao rebalanceamento: destaca mesmo com compra sugerida zero —
  // forçar um desbalanceamento temporário para aproveitar o preço é decisão do usuário.
  const discounted = asset.bazin_below_ceiling === true;
  return (
    <li className={`card ${discounted ? "card-discount" : ""}`}>
      <div className="card-head card-head-static">
        <span className="card-id">
          <span className="card-ticker">{asset.ticker}</span>
          <span className="card-name">{asset.name ?? asset.sector ?? asset.asset_class}</span>
        </span>
        {asset.suggested ? (
          <span className="card-buy">
            <Tooltip metricKey="suggested_amount">
              <strong>{money(asset.suggested.invested_exact)}</strong>
            </Tooltip>
            <span className="card-shares">
              {asset.suggested.shares} × {asset.suggested.price ? money(asset.suggested.price) : "—"}
            </span>
          </span>
        ) : (
          <span className={`card-risk ${riskClass}`} aria-label={`risco ${asset.risk_level}`} />
        )}
      </div>

      <BasketBar asset={asset} />

      {asset.bazin_ceiling_price != null && (
        <div className="card-ceiling">
          <CeilingBadge
            ceiling={asset.bazin_ceiling_price}
            price={asset.price ?? asset.suggested?.price ?? null}
            margin={asset.bazin_margin}
            belowCeiling={asset.bazin_below_ceiling}
            variant="chip"
          />
          {discounted && !asset.suggested && (
            <span className="discount-seal">Abaixo do preço-teto</span>
          )}
        </div>
      )}

      {reasons.length > 0 && (
        <ul className="card-reasons">
          {reasons.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      )}

      {discounted && !asset.suggested && (
        <p className="card-discount-note">
          Sem compra sugerida pelo rebalanceamento — mas está abaixo do teto. Antecipar é
          decisão sua.
        </p>
      )}

      {redFlags.length > 0 && (
        <ul className="card-flags">
          {redFlags.map((f, i) => (
            <li key={i}><Icon name="alert" size={13} /> {f}</li>
          ))}
        </ul>
      )}

      <div className="card-detail-link">
        <AssetLink ticker={asset.ticker}>ver detalhes de {asset.ticker} →</AssetLink>
        {asset.suggested && <RegisterBuyButton asset={asset} planId={planId} />}
      </div>
    </li>
  );
}

export function RankedList({ plan }: { plan: PlanResponse }) {
  const ranking = plan.ranking ?? [];
  const unallocated = plan.unallocated ?? 0;
  const buys = ranking.filter((a) => a.suggested);
  const rest = ranking.filter((a) => !a.suggested);
  const discountedRest = rest.filter((a) => a.bazin_below_ceiling === true).length;
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
              <AssetCard key={a.ticker} asset={a} planId={plan.plan_id} />
            ))}
          </ul>
        </>
      )}
      {rest.length > 0 && (
        <>
          <h3 className="muted">
            No alvo (sem compra sugerida)
            {discountedRest > 0 && (
              <span className="muted"> · {discountedRest} abaixo do preço-teto</span>
            )}
          </h3>
          <ul className="cards">
            {rest.map((a) => (
              <AssetCard key={a.ticker} asset={a} planId={plan.plan_id} />
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
