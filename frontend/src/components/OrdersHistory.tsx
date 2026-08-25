import { useDeleteOrder, useOrders } from "../api/queries";
import { AssetLink } from "./AssetLink";
import { isoToBR, money } from "../lib/format";

/** Sequência de meses consecutivos com aporte registrado (terminando no mês atual ou no
 *  anterior — o mês corrente ainda sem aporte não quebra a disciplina). */
export function streakMonths(dates: (string | null | undefined)[]): number {
  const months = new Set(
    dates.filter((d): d is string => !!d).map((d) => d.slice(0, 7)),
  );
  if (months.size === 0) return 0;
  let streak = 0;
  const now = new Date();
  for (let i = 0; i < 600; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    if (months.has(key)) {
      streak++;
    } else if (i === 0) {
      continue; // mês corrente ainda sem aporte: a sequência segue valendo
    } else {
      break;
    }
  }
  return streak;
}

/** Histórico de aportes executados ('já comprei') + total investido + disciplina.
 *  A sequência é um FATO sobre o histórico, não um elogio: quantos meses seguidos tiveram
 *  aporte registrado. */
export function OrdersHistory() {
  const orders = useOrders();
  const del = useDeleteOrder();
  const items = orders.data?.items ?? [];
  if (orders.isLoading || items.length === 0) return null;

  const streak = streakMonths(items.map((o) => o.executed_at));
  return (
    <div className="alloc orders-history">
      <h3>Histórico de aportes</h3>
      <p className="muted" style={{ marginTop: 0 }}>
        Total registrado: <strong>{money(orders.data?.total_invested ?? 0)}</strong>
        {streak >= 2 && (
          <span className="orders-streak"> · {streak} meses seguidos aportando</span>
        )}
      </p>
      <ul className="pf-drill-list">
        {items.slice(0, 12).map((o) => (
          <li key={o.id} className="pf-drill-item">
            <span className="pf-drill-ticker"><AssetLink ticker={o.ticker} /></span>
            <span className="muted">
              {o.shares} × {money(o.price)}
              {o.executed_at ? ` · ${isoToBR(o.executed_at.slice(0, 10))}` : ""}
            </span>
            <span className="pf-drill-val">{money(o.shares * o.price + (o.fees ?? 0))}</span>
            <button
              className="link-button"
              aria-label={`Excluir registro de ${o.ticker}`}
              disabled={del.isPending}
              onClick={() => {
                if (window.confirm(`Excluir o registro de ${o.ticker}? (não afeta o Ghostfolio)`)) {
                  del.mutate(o.id);
                }
              }}
            >
              ✕
            </button>
          </li>
        ))}
      </ul>
      {items.length > 12 && (
        <p className="muted" style={{ fontSize: 12 }}>… e mais {items.length - 12} registros.</p>
      )}
      <p className="muted" style={{ fontSize: 12 }}>
        Registro próprio do Pomar (plano × executado). Sua posição oficial continua vindo do
        Ghostfolio.
      </p>
    </div>
  );
}
