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

/** Classifica preço vs teto. Cor NUNCA sozinha — sempre acompanha texto.
 *  A margem do backend basta: antes, sem `price` (ativos não sugeridos do ranking) o
 *  chip dizia "teto não calculado" mesmo com teto e margem calculados — escondendo
 *  oportunidades Bazin de quase todo o ranking. (Exportada para teste.) */
export function classify(
  ceiling?: number | null,
  price?: number | null,
  margin?: number | null,
  belowCeiling?: boolean | null,
): { status: Status; label: string } {
  const m =
    margin != null ? margin : ceiling != null && price != null ? (ceiling - price) / ceiling : null;
  if (m == null) {
    if (belowCeiling != null) {
      return belowCeiling
        ? { status: "verde", label: "abaixo do teto" }
        : { status: "vermelho", label: "acima do teto" };
    }
    return { status: "na", label: "teto não calculado" };
  }
  if (m > 0.03) return { status: "verde", label: "abaixo do teto" };
  if (m >= -0.0001) return { status: "amarelo", label: "no teto" };
  return { status: "vermelho", label: "acima do teto" };
}

/* A marca de estado é CSS (::before com clip-path), não mais um emoji de círculo colorido.
   Três canais em vez de um: FORMA (triângulo p/ baixo = desconto, barra = no teto,
   triângulo p/ cima = caro), cor e o texto. Segue a doutrina que o app já aplica na
   comparação — a polaridade é a geometria, não a cor — e sobrevive a daltonismo e a
   impressão em preto e branco, que três círculos coloridos não sobrevivem. */
const RISK_CLASS: Record<Status, string> = {
  verde: "risk-verde",
  amarelo: "risk-amarelo",
  vermelho: "risk-vermelho",
  na: "metric-na",
};

export function CeilingBadge({ ceiling, price, margin, belowCeiling, variant = "chip" }: Props) {
  const { status, label } = classify(ceiling, price, margin, belowCeiling);
  const m =
    margin != null ? margin : ceiling != null && price != null ? (ceiling - price) / ceiling : null;
  // Convenção ÚNICA do app (glossário e ScoreBreakdown): margem POSITIVA = desconto
  // (abaixo do teto, bom). Antes o chip invertia o sinal e contradizia o tooltip.
  const marginText = m != null ? `margem ${m >= 0 ? "+" : "−"}${pct(Math.abs(m), 0)}` : null;

  if (variant === "chip") {
    const aria =
      status === "na"
        ? "Preço-teto de Bazin não calculado"
        : `${label}${marginText ? `, ${marginText}` : ""}`;
    return (
      <span className={`ceiling-chip ${RISK_CLASS[status]}`} aria-label={aria}>
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
          <div
            className="ceiling-bar"
            role="img"
            aria-label={`Preço atual ${money(price!)}, teto ${money(ceiling!)}`}
          >
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
            <strong>{label}</strong>
            {marginText ? ` · ${marginText}` : ""}
            {status === "verde" ? " (pode comprar)" : status === "vermelho" ? " (caro)" : ""}
          </p>
        </>
      ) : (
        <p className="muted">Teto não calculado: faltam anos de dividendos consistentes.</p>
      )}
    </div>
  );
}
