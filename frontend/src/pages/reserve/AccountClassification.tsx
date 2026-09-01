import { useState } from "react";
import { ApiError } from "../../api/client";
import { MutationError } from "../../components/MutationError";
import { useLabels, useSetAssignments, useUpdateAccount } from "../../api/queries";
import type { AccountSummary, AssignmentOut, Liquidity, Purpose } from "../../types";
import { Icon } from "../../components/Icon";
import { LIQUIDITY_LABEL, PURPOSE_LABEL } from "./labels";

/** Como a conta participa da carteira: se conta, para que serve e em quanto tempo o
 *  dinheiro está na mão — mais a tag de indexador, que é o item dela na cesta de renda
 *  fixa. São as três perguntas que decidem em que somas ela entra. */
export function AccountClassification({
  account,
  tag,
}: {
  account: AccountSummary;
  tag: AssignmentOut | undefined;
}) {
  const update = useUpdateAccount();
  const setAssignments = useSetAssignments();
  const indexerLabels = useLabels("indexer");
  const [open, setOpen] = useState(false);

  const patch = (body: Parameters<typeof update.mutate>[0]["body"]) =>
    update.mutate({ id: account.id, body });

  const setTag = (code: string) => {
    const label = (indexerLabels.data ?? []).find((l) => l.code === code);
    setAssignments.mutate({
      subject_type: "fi_account",
      subject_id: String(account.id),
      dimension: "indexer",
      items: label ? [{ label_id: label.id, weight: 1 }] : [],
    });
  };

  const resumo = [
    account.in_portfolio ? "conta na carteira" : "fora da carteira",
    LIQUIDITY_LABEL[account.liquidity] ?? account.liquidity,
    tag?.code ?? "sem indexador",
  ].join(" · ");

  return (
    <>
      <p className="reserve-window reserve-class">
        {resumo}{" "}
        <button className="link-button reserve-rename" onClick={() => setOpen((v) => !v)}>
          {open ? "fechar" : "editar"}
        </button>
      </p>
      {open && (
        <div className="advanced">
          <label className="class-chip class-chip-wide">
            <input
              type="checkbox"
              checked={account.counts_in_portfolio}
              disabled={account.purpose === "earmarked" || update.isPending}
              onChange={(e) => patch({ counts_in_portfolio: e.target.checked })}
            />
            <span>
              <span className="class-chip-name">Conta no patrimônio</span>
              <span className="class-chip-meta">
                {account.purpose === "earmarked"
                  ? "indisponível: a conta está reservada para outro fim"
                  : "entra nos gráficos e no cálculo dos alvos"}
              </span>
            </span>
          </label>
          <div className="adv-row">
            <label className="field">
              <span>Propósito</span>
              <select
                value={account.purpose}
                onChange={(e) => patch({ purpose: e.target.value as Purpose })}
              >
                <option value="investment">{PURPOSE_LABEL.investment}</option>
                <option value="earmarked">{PURPOSE_LABEL.earmarked}</option>
              </select>
            </label>
            <label className="field">
              <span>Liquidez</span>
              <select
                value={account.liquidity}
                onChange={(e) => patch({ liquidity: e.target.value as Liquidity })}
              >
                {account.liquidity === "unknown" && (
                  <option value="unknown">{LIQUIDITY_LABEL.unknown}</option>
                )}
                <option value="immediate">{LIQUIDITY_LABEL.immediate}</option>
                <option value="scheduled">{LIQUIDITY_LABEL.scheduled}</option>
                <option value="locked">{LIQUIDITY_LABEL.locked}</option>
              </select>
            </label>
            <label className="field">
              <span>Indexador</span>
              <select value={tag?.code ?? ""} onChange={(e) => setTag(e.target.value)}>
                <option value="">Sem indexador</option>
                {(indexerLabels.data ?? []).map((l) => (
                  <option key={l.id} value={l.code}>
                    {l.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <MutationError error={setAssignments.error} acao="salvar o indexador" />
          {update.isError && (
            <div className="banner banner-error">
              <Icon name="alert" size={15} />{" "}
              {update.error instanceof ApiError
                ? update.error.userMessage
                : "Não consegui salvar a mudança."}
            </div>
          )}
        </div>
      )}
    </>
  );
}
