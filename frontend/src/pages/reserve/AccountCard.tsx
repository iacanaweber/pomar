import { useState } from "react";
import { ConfirmButton } from "../../components/ConfirmButton";
import { MutationError } from "../../components/MutationError";
import { useArchiveAccount, useUpdateAccount } from "../../api/queries";
import type { AccountSummary, AssignmentOut } from "../../types";
import { isoToBR, money, pct } from "../../lib/format";
import { Tooltip } from "../../components/Tooltip";
import { Icon } from "../../components/Icon";
import { AccountClassification } from "./AccountClassification";
import { EntriesList } from "./EntriesList";
import { EntryForm } from "./EntryForm";
import { KIND_LABEL } from "./labels";

export function AccountCard({
  account,
  tag,
  autoOpen = false,
}: {
  account: AccountSummary;
  tag?: AssignmentOut;
  /** Veio do atalho do Plantar: abre já no formulário de lançamento. */
  autoOpen?: boolean;
}) {
  const archive = useArchiveAccount();
  const update = useUpdateAccount();
  const [open, setOpen] = useState(autoOpen);
  const [showEntries, setShowEntries] = useState(false);

  const annual = account.history_yield_annual;
  const cdiText =
    account.pct_of_cdi != null
      ? `${Math.round(account.pct_of_cdi * 100)}% do CDI`
      : annual != null && annual < 0
        ? "abaixo de zero"
        : "—";

  const days = account.history_yield_business_days ?? 0;
  const period =
    account.history_yield_from != null
      ? `Desde ${isoToBR(account.history_yield_from)} · ${days} ${days === 1 ? "dia útil" : "dias úteis"}`
      : null;

  // A última janela é curta e o usuário escolhe seu tamanho ao decidir quando atualizar o
  // saldo — anualizá-la produzia a manchete errada. Fica como caixa (R$) e período.
  const lastDays = account.last_yield_business_days ?? 0;
  const showLast =
    account.last_yield_gain != null &&
    account.last_yield_from != null &&
    account.last_yield_from !== account.history_yield_from;

  // Renomear em linha, não por `window.prompt`: a caixa nativa bloqueia, não é
  // estilizável nem testável, e em standalone aparece com o nome do host no título.
  const [renomeando, setRenomeando] = useState(false);
  const [nomeNovo, setNomeNovo] = useState(account.name);

  return (
    <li className="card">
      <div className="reserve-card-head">
        <div className="card-id">
          <span className="card-ticker">
            {renomeando ? (
              <form
                className="reserve-rename-form"
                onSubmit={(e) => {
                  e.preventDefault();
                  const nome = nomeNovo.trim();
                  if (nome && nome !== account.name)
                    update.mutate({ id: account.id, body: { name: nome } });
                  setRenomeando(false);
                }}
              >
                <input
                  value={nomeNovo}
                  onChange={(e) => setNomeNovo(e.target.value)}
                  aria-label={`Novo nome de ${account.name}`}
                  autoFocus
                />
                <button type="submit" className="link-button">
                  Salvar
                </button>
                <button
                  type="button"
                  className="link-button"
                  onClick={() => {
                    setNomeNovo(account.name);
                    setRenomeando(false);
                  }}
                >
                  Cancelar
                </button>
              </form>
            ) : (
              <>
                {account.name}{" "}
                {/* O ícone `pencil` já existia e nunca era usado, enquanto aqui havia um
                    emoji cru como rótulo inteiro do botão — exatamente o que Icon.tsx
                    proíbe por escrito. */}
                <button
                  className="link-button reserve-rename"
                  onClick={() => setRenomeando(true)}
                  aria-label={`Renomear ${account.name}`}
                >
                  <Icon name="pencil" size={16} />
                </button>
              </>
            )}
          </span>
          <span className="card-name">
            {[account.institution, account.kind ? (KIND_LABEL[account.kind] ?? account.kind) : null]
              .filter(Boolean)
              .join(" · ") || "—"}
          </span>
        </div>
        <strong className="reserve-balance">{money(account.current_balance)}</strong>
      </div>

      <div className="reserve-metrics">
        <div className="reserve-metric">
          <Tooltip metricKey="fixed_income_yield">
            <span className="muted">Rendimento</span>
          </Tooltip>
          <strong>{annual != null ? `${pct(annual)} a.a.` : "—"}</strong>
        </div>
        <div className="reserve-metric">
          <span className="muted">vs. CDI</span>
          <strong>{cdiText}</strong>
        </div>
        {account.history_yield_gain != null && (
          <div className="reserve-metric">
            <span className="muted">Ganho acumulado</span>
            <strong>{money(account.history_yield_gain)}</strong>
          </div>
        )}
      </div>

      <AccountClassification account={account} tag={tag} />

      {period && <p className="reserve-window">{period}</p>}
      {showLast && (
        <p className="reserve-window">
          Última janela: {money(account.last_yield_gain!)} em {lastDays}{" "}
          {lastDays === 1 ? "dia útil" : "dias úteis"} ({isoToBR(account.last_yield_from!)} →{" "}
          {isoToBR(account.last_yield_to!)})
          {account.last_yield_gain! < 0 && " · o IR retido num resgate cai aqui"}
        </p>
      )}

      <div className="reserve-actions">
        <button className="link-button" onClick={() => setOpen((v) => !v)}>
          {open ? "Fechar lançamento" : "Lançar aporte"}
        </button>
        <button className="link-button" onClick={() => setShowEntries((v) => !v)}>
          {showEntries ? "Ocultar lançamentos" : "Ver lançamentos"}
        </button>
        <ConfirmButton
          rotulo="Arquivar"
          pergunta="Arquivar? Os lançamentos ficam guardados."
          disabled={archive.isPending}
          onConfirm={() => archive.mutate(account.id)}
        />
      </div>

      <MutationError error={archive.error} acao={`arquivar ${account.name}`} />

      {open && <EntryForm account={account} onDone={() => setOpen(false)} />}
      {showEntries && <EntriesList accountId={account.id} />}
    </li>
  );
}
