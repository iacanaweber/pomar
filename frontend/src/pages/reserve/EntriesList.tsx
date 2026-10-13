import { ConfirmButton } from "../../components/ConfirmButton";
import { MutationError } from "../../components/MutationError";
import { useDeleteEntry, useEntries } from "../../api/queries";
import { isoToBR, money } from "../../lib/format";
import { ENTRY_LABEL } from "./labels";
import { Skeleton } from "../../components/Skeleton";

/** Lista de lançamentos de uma conta, com remoção (corrigir erros). */
export function EntriesList({ accountId }: { accountId: number }) {
  const { data, isLoading } = useEntries(accountId);
  const del = useDeleteEntry();
  if (isLoading)
    return (
      <div className="entries-pad">
        <Skeleton blocks={["line", "line"]} label="Carregando lançamentos" />
      </div>
    );
  const items = data?.items ?? [];
  if (!items.length) return <p className="muted entries-pad">Nenhum lançamento ainda.</p>;
  return (
    <ul className="reserve-entries">
      {items.map((e) => (
        <li key={e.id} className="reserve-entry">
          <span className={`reserve-entry-tag tag-${e.kind}`}>{ENTRY_LABEL[e.kind] ?? e.kind}</span>
          <span className="reserve-entry-date">{isoToBR(e.entry_date)}</span>
          <strong className="reserve-entry-amount">{money(e.amount)}</strong>
          <ConfirmButton
            className="link-button reserve-archive"
            rotulo={`Remover ${ENTRY_LABEL[e.kind] ?? "lançamento"} de ${isoToBR(e.entry_date)}`}
            pergunta="Remover? Saldo e rendimento serão recalculados."
            icone="trash"
            disabled={del.isPending}
            onConfirm={() => del.mutate({ accountId, entryId: e.id })}
          />
        </li>
      ))}
      <MutationError error={del.error} acao="remover o lançamento" />
    </ul>
  );
}
