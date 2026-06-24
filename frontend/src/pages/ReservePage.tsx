import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import {
  useAddEntry,
  useArchiveAccount,
  useCreateAccount,
  useFixedIncome,
} from "../api/queries";
import type { AccountSummary } from "../types";
import { money, parseBRL, pct } from "../lib/format";
import { Tooltip } from "../components/Tooltip";

const KIND_LABEL: Record<string, string> = {
  cdb: "CDB",
  tesouro: "Tesouro",
  poupanca: "Poupança",
  conta: "Conta",
  outro: "Outro",
};

/** Formulário inline de lançamento (atualizar saldo / aporte / resgate) numa conta. */
function EntryForm({ account, onDone }: { account: AccountSummary; onDone: () => void }) {
  const addEntry = useAddEntry();
  const [kind, setKind] = useState<"balance" | "deposit" | "withdrawal">("balance");
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState("");

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const value = parseBRL(amount);
    if (!(value > 0)) return;
    addEntry.mutate(
      { id: account.id, body: { kind, amount: value, entry_date: date || null } },
      { onSuccess: () => { setAmount(""); onDone(); } },
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
          <input inputMode="decimal" placeholder="ex.: 1.000,00" value={amount} onChange={(e) => setAmount(e.target.value)} />
        </label>
        <label className="field">
          <span>Data (opcional)</span>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </label>
      </div>
      <p className="strategy-desc" style={{ marginTop: 0 }}>
        {kind === "balance"
          ? "Informe o saldo que aparece hoje no app do banco — calculamos o rendimento desde o último."
          : kind === "deposit"
          ? "Dinheiro novo que você colocou (não conta como rendimento)."
          : "Dinheiro que você sacou."}
      </p>
      {addEntry.isError && (
        <div className="banner banner-error">
          ⚠️ {addEntry.error instanceof ApiError ? addEntry.error.userMessage : "Erro ao lançar."}
        </div>
      )}
      <button className="primary" type="submit" disabled={addEntry.isPending || !(parseBRL(amount) > 0)}>
        {addEntry.isPending ? "Salvando…" : "Salvar lançamento"}
      </button>
    </form>
  );
}

function AccountCard({ account, cdiAnnual }: { account: AccountSummary; cdiAnnual?: number | null }) {
  const archive = useArchiveAccount();
  const [open, setOpen] = useState(false);

  const pctCdiText =
    account.pct_of_cdi != null ? `${Math.round(account.pct_of_cdi * 100)}% do CDI` : null;

  return (
    <li className="card">
      <div className="reserve-card-head">
        <div className="card-id">
          <span className="card-ticker">{account.name}</span>
          <span className="card-name">
            {[account.institution, account.kind ? KIND_LABEL[account.kind] ?? account.kind : null]
              .filter(Boolean)
              .join(" · ") || "—"}
          </span>
        </div>
        <strong className="reserve-balance">{money(account.current_balance)}</strong>
      </div>

      <div className="reserve-metrics">
        <div className="reserve-metric">
          <Tooltip metricKey="net_yield">
            <span className="muted">Último rendimento</span>
          </Tooltip>
          <strong>
            {account.last_yield_annual != null ? `${pct(account.last_yield_annual)} a.a.` : "—"}
          </strong>
        </div>
        <div className="reserve-metric">
          <span className="muted">vs. CDI</span>
          <strong>{pctCdiText ?? "—"}</strong>
        </div>
        {account.last_yield_gain != null && (
          <div className="reserve-metric">
            <span className="muted">Ganho no período</span>
            <strong>{money(account.last_yield_gain)}</strong>
          </div>
        )}
      </div>

      <div className="reserve-actions">
        <button className="link-button" onClick={() => setOpen((v) => !v)}>
          {open ? "▲ Fechar lançamento" : "＋ Lançar aporte / atualizar saldo"}
        </button>
        <button
          className="link-button reserve-archive"
          onClick={() => {
            if (confirm(`Arquivar a conta "${account.name}"?`)) archive.mutate(account.id);
          }}
          disabled={archive.isPending}
          aria-label={`Arquivar conta ${account.name}`}
        >
          🗑 Arquivar
        </button>
      </div>

      {open && <EntryForm account={account} onDone={() => setOpen(false)} />}

      {cdiAnnual != null && account.last_yield_annual == null && (
        <p className="strategy-desc" style={{ padding: "0 14px 12px" }}>
          Lance um saldo para calcularmos o rendimento (CDI hoje: {pct(cdiAnnual)} a.a.).
        </p>
      )}
    </li>
  );
}

function NewAccountForm() {
  const create = useCreateAccount();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [institution, setInstitution] = useState("");
  const [kind, setKind] = useState("cdb");

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    create.mutate(
      { name: name.trim(), institution: institution.trim() || null, kind, benchmark: "cdi" },
      {
        onSuccess: () => {
          setName("");
          setInstitution("");
          setOpen(false);
        },
      },
    );
  };

  if (!open)
    return (
      <button className="primary" onClick={() => setOpen(true)}>
        ＋ Adicionar conta / aplicação
      </button>
    );

  return (
    <form className="controls" onSubmit={submit}>
      <label className="field">
        <span>Nome da aplicação</span>
        <input placeholder="ex.: CDB Banco X, Tesouro Selic 2029" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
      </label>
      <div className="adv-row">
        <label className="field">
          <span>Instituição (opcional)</span>
          <input placeholder="ex.: Nubank" value={institution} onChange={(e) => setInstitution(e.target.value)} />
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
      {create.isError && (
        <div className="banner banner-error">
          ⚠️ {create.error instanceof ApiError ? create.error.userMessage : "Erro ao criar a conta."}
        </div>
      )}
      <div className="reserve-actions">
        <button className="primary" type="submit" disabled={create.isPending || !name.trim()}>
          {create.isPending ? "Criando…" : "Criar conta"}
        </button>
        <button className="link-button" type="button" onClick={() => setOpen(false)}>
          Cancelar
        </button>
      </div>
    </form>
  );
}

export function ReservePage() {
  const navigate = useNavigate();
  const { data, isLoading, error } = useFixedIncome();

  const accounts = (data?.accounts ?? []).filter((a) => !a.archived);

  return (
    <main className="page">
      <button className="link-button" onClick={() => navigate(-1)}>
        ← voltar
      </button>
      <h2>Reserva de renda fixa</h2>
      <p className="muted" style={{ marginTop: 0 }}>
        No método Barsi/Bazin, a reserva (CDI/Tesouro/CDB) vem antes da renda variável. Acompanhe
        aqui suas aplicações e o rendimento de cada uma.
      </p>

      {isLoading && <p className="muted">Carregando suas aplicações…</p>}
      {error && (
        <div className="banner banner-error">
          ⚠️ {error instanceof ApiError ? error.userMessage : "Erro ao ler a renda fixa."}
        </div>
      )}

      {data && (
        <div className="pf-summary">
          <span className="muted">Total em reserva</span>
          <strong className="pf-total">{money(data.total_balance)}</strong>
          {data.cdi_annual != null && (
            <span className="muted">CDI de referência: {pct(data.cdi_annual)} a.a.</span>
          )}
        </div>
      )}

      {data && accounts.length === 0 && (
        <div className="banner banner-warn">
          Nenhuma aplicação ainda. Adicione sua reserva (conta, CDB, Tesouro) para acompanhar o
          rendimento e comparar com o CDI.
        </div>
      )}

      {accounts.length > 0 && (
        <ul className="cards" style={{ marginBottom: 16 }}>
          {accounts.map((a) => (
            <AccountCard key={a.id} account={a} cdiAnnual={data?.cdi_annual} />
          ))}
        </ul>
      )}

      <NewAccountForm />

      <p className="disclaimer">
        Rendimentos calculados a partir dos saldos que você informa. Não é recomendação de
        investimento.
      </p>
    </main>
  );
}
