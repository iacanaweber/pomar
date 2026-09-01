import { useState, type FormEvent } from "react";
import { ApiError } from "../../api/client";
import { useAddEntry, useCreateAccount } from "../../api/queries";
import type { NewLiquidity, Purpose } from "../../types";
import { brToISO, parseBRL, todayBR } from "../../lib/format";
import { Icon } from "../../components/Icon";
import { LIQUIDITY_LABEL, PURPOSE_LABEL } from "./labels";

export function NewAccountForm() {
  const create = useCreateAccount();
  const addEntry = useAddEntry();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [institution, setInstitution] = useState("");
  const [kind, setKind] = useState("cdb");
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState(todayBR());
  // Liquidez é obrigatória no cadastro novo: sem ela o app não sabe se este dinheiro
  // atende a uma emergência, e passaria a chutar.
  const [liquidity, setLiquidity] = useState<NewLiquidity>("immediate");
  const [purpose, setPurpose] = useState<Purpose>("investment");
  const [counts, setCounts] = useState(true);

  const busy = create.isPending || addEntry.isPending;
  const dateInvalid = date.trim() !== "" && brToISO(date) === null;
  const earmarked = purpose === "earmarked";

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim() || dateInvalid) return;
    const value = parseBRL(amount);
    create.mutate(
      {
        name: name.trim(),
        institution: institution.trim() || null,
        kind,
        benchmark: "cdi",
        liquidity,
        purpose,
        counts_in_portfolio: earmarked ? false : counts,
      },
      {
        onSuccess: (acc) => {
          // Se informou um saldo inicial, já registra como 1º "saldo" datado — assim a
          // PRÓXIMA atualização de saldo já calcula o rendimento (precisa de 2 datas).
          if (value > 0) {
            addEntry.mutate({
              id: acc.id,
              body: { kind: "balance", amount: value, entry_date: brToISO(date) },
            });
          }
          setName("");
          setInstitution("");
          setAmount("");
          setDate(todayBR());
          setOpen(false);
        },
      },
    );
  };

  if (!open)
    return (
      <button className="primary" onClick={() => setOpen(true)}>
        Adicionar conta
      </button>
    );

  return (
    <form className="controls" onSubmit={submit}>
      <label className="field">
        <span>Nome da aplicação</span>
        <input
          placeholder="ex.: CDB Banco X, Tesouro Selic 2029"
          value={name}
          onChange={(e) => setName(e.target.value)}
          autoFocus
        />
      </label>
      <div className="adv-row">
        <label className="field">
          <span>Instituição (opcional)</span>
          <input
            placeholder="ex.: Nubank"
            value={institution}
            onChange={(e) => setInstitution(e.target.value)}
          />
        </label>
        <label className="field">
          <span>Tipo</span>
          <select value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="cdb">CDB</option>
            <option value="tesouro">Tesouro Direto</option>
            <option value="poupanca">Poupança</option>
            <option value="conta">Conta / caixa</option>
            <option value="outro">Outro</option>
          </select>
        </label>
      </div>
      <div className="adv-row">
        <label className="field">
          <span>Liquidez</span>
          <select value={liquidity} onChange={(e) => setLiquidity(e.target.value as NewLiquidity)}>
            <option value="immediate">{LIQUIDITY_LABEL.immediate}</option>
            <option value="scheduled">{LIQUIDITY_LABEL.scheduled}</option>
            <option value="locked">{LIQUIDITY_LABEL.locked}</option>
          </select>
        </label>
        <label className="field">
          <span>Propósito</span>
          <select value={purpose} onChange={(e) => setPurpose(e.target.value as Purpose)}>
            <option value="investment">{PURPOSE_LABEL.investment}</option>
            <option value="earmarked">{PURPOSE_LABEL.earmarked}</option>
          </select>
        </label>
      </div>
      <label className="class-chip class-chip-wide">
        <input
          type="checkbox"
          checked={earmarked ? false : counts}
          disabled={earmarked}
          onChange={(e) => setCounts(e.target.checked)}
        />
        <span>
          <span className="class-chip-name">Conta no patrimônio</span>
          <span className="class-chip-meta">
            {earmarked
              ? "indisponível: dinheiro reservado para outro fim não entra na carteira"
              : "entra nos gráficos e no cálculo dos alvos"}
          </span>
        </span>
      </label>
      <div className="adv-row">
        <label className="field">
          <span>Saldo de partida (R$, opcional)</span>
          <input
            inputMode="decimal"
            placeholder="ex.: 10.000,00"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
          />
        </label>
        <label className="field">
          <span>Data desse saldo</span>
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
        Use a data real da aplicação.
      </p>
      {(create.isError || addEntry.isError) && (
        <div className="banner banner-error">
          <Icon name="alert" size={15} />{" "}
          {create.error instanceof ApiError ? create.error.userMessage : "Erro ao criar a conta."}
        </div>
      )}
      <div className="reserve-actions">
        <button className="primary" type="submit" disabled={busy || !name.trim() || dateInvalid}>
          {busy ? "Criando" : "Criar conta"}
        </button>
        <button className="link-button" type="button" onClick={() => setOpen(false)}>
          Cancelar
        </button>
      </div>
    </form>
  );
}
