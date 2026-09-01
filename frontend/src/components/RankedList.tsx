import type { PlanAsset, PlanResponse } from "../types";
import { classLabel, temMetricasDeAcao } from "../lib/classes";
import { money, pct } from "../lib/format";
import { useComprasFeitas } from "../hooks/useComprasFeitas";
import { AssetLink } from "./AssetLink";
import { Tooltip } from "./Tooltip";
import { Icon } from "./Icon";

const RISK_CLASS: Record<string, string> = {
  verde: "risk-verde",
  amarelo: "risk-amarelo",
  vermelho: "risk-vermelho",
};

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
      <div
        className="basket-bar"
        role="img"
        aria-label={`peso na cesta: ${pct(current)}, alvo ${pct(target)}`}
      >
        {grew && <span className="basket-bar-after" style={{ width: w(after) }} />}
        <span className="basket-bar-now" style={{ width: w(current) }} />
        <span className="basket-bar-target" style={{ left: w(target) }} />
      </div>
      <span className="basket-bar-legend muted">
        na cesta de {classLabel(asset.asset_class ?? "")}: {pct(current)}
        {grew ? ` → ${pct(after!)}` : ""} · alvo {pct(target)}
      </span>
    </div>
  );
}

function AssetCard({
  asset,
  feito,
  onAlternar,
}: {
  asset: PlanAsset;
  feito: boolean;
  onAlternar: () => void;
}) {
  const reasons = asset.reasons ?? [];
  const redFlags = asset.red_flags ?? [];
  const riskClass = RISK_CLASS[asset.risk_level ?? "verde"] ?? "";
  // Preço-teto só aparece em ação e FII — o legado. Numa carteira de ETF de acumulação
  // ele não dirige compra nenhuma, e liderar o card com ele era a interface contando uma
  // estratégia que não é mais a do usuário. O que dirige a compra é o peso na cesta,
  // logo abaixo, na BasketBar.
  const discounted = temMetricasDeAcao(asset.asset_class) && asset.bazin_below_ceiling === true;
  return (
    <li className={`card ${discounted ? "card-discount" : ""} ${feito ? "card-feito" : ""}`}>
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
              {asset.suggested.shares} ×{" "}
              {asset.suggested.price ? money(asset.suggested.price) : "—"}
            </span>
          </span>
        ) : (
          <span className={`card-risk ${riskClass}`} aria-label={`risco ${asset.risk_level}`} />
        )}
      </div>

      <BasketBar asset={asset} />

      {reasons.length > 0 && (
        <ul className="card-reasons">
          {reasons.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      )}

      {redFlags.length > 0 && (
        <ul className="card-flags">
          {redFlags.map((f, i) => (
            <li key={i}>
              <Icon name="alert" size={13} /> {f}
            </li>
          ))}
        </ul>
      )}

      <div className="card-detail-link">
        <AssetLink ticker={asset.ticker}>ver detalhes de {asset.ticker} →</AssetLink>
        {/* Conferência, não registro: a posição oficial é o Ghostfolio. Isto só marca o
            que já foi executado na corretora, para não comprar duas vezes nem esquecer
            uma. Mesmo idioma de checkbox do seletor de classes (`.class-chip`). */}
        {asset.suggested && (
          <label className={`card-ack ${feito ? "card-ack-on" : ""}`}>
            <input type="checkbox" checked={feito} onChange={onAlternar} />
            <span>já comprei</span>
          </label>
        )}
      </div>
    </li>
  );
}

export function RankedList({ plan }: { plan: PlanResponse }) {
  // A renda fixa tem cartão próprio, e é lá que ela se resolve por inteiro: o valor do
  // piso, as tags e as cotas do ETF, somando o total da classe. Repetir o ETF aqui, entre
  // BBAS3 e VWRA11, quebraria essa soma em dois lugares e faria a lista de compras da
  // bolsa parecer conter uma compra que não é de bolsa. O `ranking` do backend continua
  // completo — é o registro do que o plano decidiu.
  const ranking = (plan.ranking ?? []).filter((a) => a.asset_class !== "RENDA_FIXA");
  const unallocated = plan.unallocated ?? 0;
  const buys = ranking.filter((a) => a.suggested);
  const rest = ranking.filter((a) => !a.suggested);

  const comprei = useComprasFeitas(plan.plan_id);
  // Só as compras sugeridas contam no progresso: o que está no alvo não tem nada a fazer.
  const feitas = buys.filter((a) => comprei.feito(a.ticker)).length;
  const tudoFeito = buys.length > 0 && feitas === buys.length;

  return (
    <div className="ranked">
      {buys.length > 0 && (
        <>
          <h2>
            Compras sugeridas para {money(plan.aporte)}
            {unallocated > 0 && <span className="muted"> · sobra {money(unallocated)}</span>}
          </h2>
          {/* Cumprido, se cala: com tudo marcado a frase para de contar e confirma —
              mesmo idioma de `.reserve-goal.goal-met`. */}
          <p
            className={`ranked-progresso ${tudoFeito ? "ranked-progresso-fim" : ""}`}
            role="status"
          >
            {tudoFeito ? "Tudo comprado." : `${feitas} de ${buys.length} feitas`}
          </p>
          <ul className="cards">
            {buys.map((a) => (
              <AssetCard
                key={a.ticker}
                asset={a}
                feito={comprei.feito(a.ticker)}
                onAlternar={() => comprei.alternar(a.ticker)}
              />
            ))}
          </ul>
        </>
      )}
      {rest.length > 0 && (
        <>
          <h3 className="muted">No alvo (sem compra sugerida)</h3>
          <ul className="cards">
            {rest.map((a) => (
              <AssetCard
                key={a.ticker}
                asset={a}
                feito={comprei.feito(a.ticker)}
                onAlternar={() => comprei.alternar(a.ticker)}
              />
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
