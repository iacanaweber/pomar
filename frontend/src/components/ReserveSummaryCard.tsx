import { Link } from "react-router-dom";
import type { ReserveSuggestion } from "../types";
import { money, pct } from "../lib/format";
import { Tooltip } from "./Tooltip";

/** Card da sugestão de reserva no plano: quanto do aporte vai à reserva vs renda variável. */
export function ReserveSummaryCard({ reserve, currency = "BRL" }: { reserve: ReserveSuggestion; currency?: string }) {
  const filled = Math.min(Math.round(reserve.pct_filled * 100), 100);
  const directed = reserve.directed_now > 0;
  return (
    <div className="alloc reserve-suggestion">
      <h3>
        <Tooltip metricKey="reserve_target">
          <span>Reserva / renda fixa primeiro</span>
        </Tooltip>
      </h3>
      <div
        className="goal-bar"
        role="progressbar"
        aria-valuenow={filled}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Reserva ${filled}% preenchida`}
      >
        <div className="alloc-track" style={{ height: 16 }}>
          <div className="alloc-cur" style={{ width: `${filled}%`, background: reserve.gap > 0 ? "var(--leaf)" : "var(--green)" }} />
        </div>
        <span className="goal-bar-label">
          {money(reserve.current_amount, currency)} de {money(reserve.target_amount, currency)} · {filled}%
        </span>
      </div>

      {directed ? (
        <p className="goal-status">
          Deste aporte, direcione <strong>{money(reserve.directed_now, currency)}</strong> à reserva
          antes da renda variável. Faltam {money(reserve.gap, currency)} para a reserva-alvo.
        </p>
      ) : (
        <p className="goal-status risk-verde">
          ✓ Reserva completa. Pode focar o aporte na renda variável.
        </p>
      )}

      <p className="strategy-desc" style={{ margin: "4px 0 0" }}>
        {reserve.note}
        {reserve.benchmark_cdi_annual != null && ` · CDI ${pct(reserve.benchmark_cdi_annual)} a.a.`}
      </p>
      <p style={{ margin: "8px 0 0" }}>
        <Link to="/reserva" className="asset-link">Gerenciar minha reserva →</Link>
      </p>
    </div>
  );
}
