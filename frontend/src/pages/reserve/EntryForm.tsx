import { useState, type FormEvent } from "react";
import { ApiError } from "../../api/client";
import { useAddEntry } from "../../api/queries";
import type { AccountSummary } from "../../types";
import { brToISO, parseBRL, todayBR } from "../../lib/format";
import { Icon } from "../../components/Icon";

/** Formulário inline de lançamento (atualizar saldo / aporte / resgate) numa conta. */
export function EntryForm({ account, onDone }: { account: AccountSummary; onDone: () => void }) {
  const addEntry = useAddEntry();
  const [kind, setKind] = useState<"balance" | "deposit" | "withdrawal">("balance");
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState(todayBR());

  const dateInvalid = date.trim() !== "" && brToISO(date) === null;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const value = parseBRL(amount);
    if (!(value > 0) || dateInvalid) return;
    addEntry.mutate(
      { id: account.id, body: { kind, amount: value, entry_date: brToISO(date) } },
      {
        onSuccess: () => {
          setAmount("");
          onDone();
        },
      },
    );
  };

  return (
    <form className="advanced" onSubmit={submit}>
      <div className="adv-row">
        <label className="field">
          <span>Tipo de lançamento</span>
          <select value={kind} onChange={(e) => setKind(e.target.value as typeof kind)}>
            <option value="balance">Atualizar saldo (valor atual)</option>
            <option value="deposit">Aporte (depósito)</option>
            <option value="withdrawal">Resgate (saque)</option>
          </select>
        </label>
        <label className="field">
          <span>Valor (R$)</span>
          <input
            inputMode="decimal"
            placeholder="ex.: 1.000,00"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
          />
        </label>
        <label className="field">
          <span>Data do saldo</span>
          <input
            inputMode="numeric"
            placeholder="dd/mm/aaaa"
            maxLength={10}
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
          {dateInvalid && <span className="field-error">Use o formato dd/mm/aaaa.</span>}
        </label>
      </div>
      <p className="note-desc" style={{ marginTop: 0 }}>
        {kind === "balance"
          ? "Saldo atual. Com um saldo anterior em outra data, o rendimento sai da diferença."
          : kind === "deposit"
            ? "Dinheiro novo. Não conta como rendimento."
            : "Dinheiro sacado."}
      </p>
      {addEntry.isError && (
        <div className="banner banner-error">
          <Icon name="alert" size={15} />{" "}
          {addEntry.error instanceof ApiError ? addEntry.error.userMessage : "Erro ao lançar."}
        </div>
      )}
      <button
        className="primary"
        type="submit"
        disabled={addEntry.isPending || !(parseBRL(amount) > 0) || dateInvalid}
      >
        {addEntry.isPending ? "Salvando" : "Salvar lançamento"}
      </button>
    </form>
  );
}
