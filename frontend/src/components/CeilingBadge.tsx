import { money, pct } from "../lib/format";
import { Tooltip } from "./Tooltip";

interface Props {
  /** Preço-teto de Bazin (BRL). */
  ceiling?: number | null;
  /** Preço atual de mercado (BRL). */
  price?: number | null;
  /** Margem sobre o teto em [-1,1] (positivo = abaixo do teto, com desconto). */
  margin?: number | null;
  /** Backend pode já dizer se está abaixo do teto. */
  belowCeiling?: boolean | null;
  /** "chip" = compacto (cards do ranking); "block" = bloco completo (página do ativo). */
  variant?: "chip" | "block";
}

type Status = "verde" | "amarelo" | "vermelho" | "na";

/** Classifica preço vs teto. Cor NUNCA sozinha — sempre acompanha texto. */
function classify(ceiling?: number | null, price?: number | null, margin?: number | null): {
  status: Status;
  label: string;
} {
  if (ceiling == null || price == null) {
    return { status: "na", label: "teto não calculado" };
  }
  // margem = (teto - preço) / teto; quando não vier, calculamos.
  const m = margin != null ? margin : (ceiling - price) / ceiling;
  if (m > 0.03) return { status: "verde", label: "abaixo do teto" };
  if (m >= -0.0001) return { status: "amarelo", label: "no teto" };
  return { status: "vermelho", label: "acima do teto" };
}

const ICON: Record<Status, string> = {
  verde: "🟢",
  amarelo: "🟡",
  vermelho: "🔴",
  na: "⚪",
};
const RISK_CLASS: Record<Status, string> = {
  verde: "risk-verde",
  amarelo: "risk-amarelo",
  vermelho: "risk-vermelho",
  na: "metric-na",
};

export function CeilingBadge({ ceiling, price, margin, variant = "chip" }: Props) {
  const { status, label } = classify(ceiling, price, margin);
  const m = margin != null ? margin : ceiling != null && price != null ? (ceiling - price) / ceiling : null;
  const marginText = m != null ? `${m >= 0 ? "−" : "+"}${pct(Math.abs(m), 0)}` : null;

  if (variant === "chip") {
    const aria =
      status === "na"
        ? "Preço-teto de Bazin não calculado"
        : `${label}${marginText ? `, margem ${marginText}` : ""}`;
    return (
      <span className={`ceiling-chip ${RISK_CLASS[status]}`} aria-label={aria}>
        <span aria-hidden="true">{ICON[status]}</span>
        <span>
          {label}
          {status !== "na" && marginText ? ` (${marginText})` : ""}
        </span>
      </span>
    );
  }

  // Bloco completo (AssetPage): barra preço atual vs teto + selo + margem.
  const hasBar = ceiling != null && price != null;
  // posição do marcador do teto na barra (0..100); escala até 1.3× o teto p/ folga.
  const scaleMax = hasBar ? Math.max(ceiling!, price!) * 1.15 : 1;
  const tgtPct = hasBar ? Math.min((ceiling! / scaleMax) * 100, 100) : 0;
  const curPct = hasBar ? Math.min((price! / scaleMax) * 100, 100) : 0;

  return (
    <div className="ceiling-block alloc">
      <h3>
        <Tooltip metricKey="bazin_ceiling_price">
          <span>Preço-teto de Bazin</span>
        </Tooltip>
      </h3>

      {hasBar ? (
        <>
          <div className="ceiling-bar" role="img" aria-label={`Preço atual ${money(price!)}, teto ${money(ceiling!)}`}>
            <div className="alloc-track" style={{ height: 18 }}>
              <div className="alloc-cur" style={{ width: `${curPct}%` }} />
              <div className="alloc-tgt" style={{ left: `${tgtPct}%`, height: 26, top: -4 }} />
            </div>
            <div className="ceiling-bar-labels">
              <span>
                atual <strong>{money(price!)}</strong>
              </span>
              <span className="muted">
                teto <strong>{money(ceiling!)}</strong>
              </span>
            </div>
          </div>
          <p className={`ceiling-verdict ${RISK_CLASS[status]}`}>
            <span aria-hidden="true">{ICON[status]}</span>{" "}
            <strong>{label.toUpperCase()}</strong>
            {marginText ? ` · margem ${marginText}` : ""}
            {status === "verde" ? " (pode comprar)" : status === "vermelho" ? " (caro)" : ""}
          </p>
        </>
      ) : (
        <p className="muted">
          Teto não calculado — faltam anos de dividendos consistentes para estimar com segurança.
        </p>
      )}
    </div>
  );
}
