import { useDeleteOrder, useOrders } from "../api/queries";
import { AssetLink } from "./AssetLink";
import { isoToBR, money } from "../lib/format";
import { ConfirmButton } from "./ConfirmButton";
import { MutationError } from "./MutationError";

/** Histórico de aportes executados ('já comprei') e total investido. */
export function OrdersHistory() {
  const orders = useOrders();
  const del = useDeleteOrder();
  const items = orders.data?.items ?? [];
  // Falha e vazio eram a MESMA coisa (`isLoading || length === 0` devolvia null), então
  // um histórico que não carregou parecia um histórico que não existe.
  if (orders.isError)
    return (
      <p className="muted orders-erro" role="status">
        Histórico de aportes indisponível.{" "}
        <button className="link-button" onClick={() => orders.refetch()}>
          Tentar de novo
        </button>
      </p>
    );
  if (orders.isLoading || items.length === 0) return null;

  return (
    <div className="alloc orders-history">
      <h3>Histórico de aportes</h3>
      <MutationError error={del.error} acao="apagar o registro" />
      <p className="muted" style={{ marginTop: 0 }}>
        Total registrado: <strong>{money(orders.data?.total_invested ?? 0)}</strong>
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
            <ConfirmButton
              rotulo={`Excluir registro de ${o.ticker}`}
              pergunta="Excluir? Não afeta o Ghostfolio."
              icone="close"
              disabled={del.isPending}
              onConfirm={() => del.mutate(o.id)}
            />
          </li>
        ))}
      </ul>
      {items.length > 12 && (
        <p className="muted" style={{ fontSize: 12 }}>+{items.length - 12} registros</p>
      )}
      <p className="muted" style={{ fontSize: 12 }}>
        Registro local. Posição oficial: Ghostfolio.
      </p>
    </div>
  );
}
