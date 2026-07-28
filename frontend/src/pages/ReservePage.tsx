import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import {
  useAddEntry,
  useArchiveAccount,
  useCreateAccount,
  useDeleteEntry,
  useEntries,
  useFixedIncome,
  usePortfolio,
  usePreferences,
  useSavePreferences,
  useUpdateAccount,
} from "../api/queries";
import type { AccountSummary } from "../types";
import { brToISO, isoToBR, money, parseBRL, pct, todayBR } from "../lib/format";
import { Tooltip } from "../components/Tooltip";

/** Barra alvo × atual da reserva, NA PRÓPRIA página (antes só existia dentro do plano e
 *  só com alvo configurado nos ajustes avançados — a J4 'como está minha reserva?' não
 *  tinha tela). Permite definir/editar o alvo aqui mesmo. */
function ReserveGoal({ totalReserve }: { totalReserve: number }) {
  const prefs = usePreferences();
  const savePrefs = useSavePreferences();
  const portfolio = usePortfolio();
  const [editing, setEditing] = useState(false);
  const [targetPct, setTargetPct] = useState<number | null>(null);

  const savedTarget = prefs.data?.reserve_target ?? 0;
  const shownPct = targetPct ?? Math.round(savedTarget * 100);
  const totalRV = portfolio.data?.total_value ?? 0;

  const save = () => {
    savePrefs.mutate(
      { reserve_target: (shownPct || 0) / 100 },
      { onSuccess: () => setEditing(false) },
    );
  };

  if (savedTarget <= 0 && !editing) {
    return (
      <div className="alloc reserve-goal">
        <p className="muted" style={{ margin: 0 }}>
          Sem reserva-alvo definida. No método Barsi, completar a reserva vem <strong>antes</strong>{" "}
          da renda variável — defina um alvo e o plano prioriza automaticamente.
        </p>
        <button className="link-button" onClick={() => setEditing(true)}>
          Definir reserva-alvo
        </button>
      </div>
    );
  }

  const targetAmount = (shownPct / 100) * (totalRV + totalReserve);
  const gap = Math.max(0, targetAmount - totalReserve);
  const filled = targetAmount > 0 ? Math.min(1, totalReserve / targetAmount) : 1;

  return (
    <div className="alloc reserve-goal">
      <div className="goal-head">
        <Tooltip metricKey="reserve_target">
          <h3 style={{ margin: 0 }}>Meta da reserva</h3>
        </Tooltip>
        {!editing && (
          <button className="link-button" onClick={() => setEditing(true)}>editar</button>
        )}
      </div>
      {editing ? (
        <div className="reserve-actions" style={{ alignItems: "center" }}>
          <label className="field" style={{ maxWidth: 160 }}>
            <span>Reserva-alvo (% do patrimônio)</span>
            <input
              type="number"
              min={0}
              max={100}
              value={shownPct}
              onChange={(e) => setTargetPct(Number(e.target.value))}
              autoFocus
            />
          </label>
          <button className="primary" onClick={save} disabled={savePrefs.isPending}>
            {savePrefs.isPending ? "Salvando…" : "Salvar"}
          </button>
          <button className="link-button" onClick={() => { setEditing(false); setTargetPct(null); }}>
            Cancelar
          </button>
        </div>
      ) : (
        <>
          <div className="goal-bar" role="progressbar" aria-valuenow={Math.round(filled * 100)}
               aria-valuemin={0} aria-valuemax={100} aria-label={`Reserva: ${Math.round(filled * 100)}% do alvo`}>
            <div className="alloc-track" style={{ height: 18 }}>
              <div className="alloc-cur" style={{ width: `${Math.round(filled * 100)}%`,
                background: filled >= 1 ? "var(--green)" : "var(--leaf)" }} />
            </div>
            <span className="goal-bar-label">{Math.round(filled * 100)}% do alvo</span>
          </div>
          <p className="goal-status" style={{ marginBottom: 0 }}>
            Alvo: <strong>{money(targetAmount)}</strong> ({shownPct}% do patrimônio) · atual{" "}
            <strong>{money(totalReserve)}</strong>
            {gap > 0 ? <> · faltam <strong>{money(gap)}</strong></> : <> · ✅ completa</>}
          </p>
          {portfolio.isError && (
            <p className="muted" style={{ fontSize: 12 }}>
              (carteira indisponível — o alvo considera só a reserva por enquanto)
            </p>
          )}
        </>
      )}
    </div>
  );
}

const ENTRY_LABEL: Record<string, string> = {
  balance: "Saldo",
  deposit: "Aporte",
  withdrawal: "Resgate",
};

/** Lista de lançamentos de uma conta, com remoção (corrigir erros). */
function EntriesList({ accountId }: { accountId: number }) {
  const { data, isLoading } = useEntries(accountId);
  const del = useDeleteEntry();
  if (isLoading) return <p className="muted" style={{ padding: "0 14px 12px" }}>Carregando lançamentos…</p>;
  const items = data?.items ?? [];
  if (!items.length)
    return <p className="muted" style={{ padding: "0 14px 12px" }}>Nenhum lançamento ainda.</p>;
  return (
    <ul className="reserve-entries">
      {items.map((e) => (
        <li key={e.id} className="reserve-entry">
          <span className={`reserve-entry-tag tag-${e.kind}`}>{ENTRY_LABEL[e.kind] ?? e.kind}</span>
          <span className="reserve-entry-date">{isoToBR(e.entry_date)}</span>
          <strong className="reserve-entry-amount">{money(e.amount)}</strong>
          <button
            className="link-button reserve-archive"
            aria-label={`Remover ${ENTRY_LABEL[e.kind] ?? "lançamento"} de ${isoToBR(e.entry_date)}`}
            disabled={del.isPending}
            onClick={() => {
              if (confirm("Remover este lançamento? O saldo e o rendimento serão recalculados."))
                del.mutate({ accountId, entryId: e.id });
            }}
          >
            🗑
          </button>
        </li>
      ))}
    </ul>
  );
}

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
  const [date, setDate] = useState(todayBR());

  const dateInvalid = date.trim() !== "" && brToISO(date) === null;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const value = parseBRL(amount);
    if (!(value > 0) || dateInvalid) return;
    addEntry.mutate(
      { id: account.id, body: { kind, amount: value, entry_date: brToISO(date) } },
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
          <span>Data do saldo</span>
          <input inputMode="numeric" placeholder="dd/mm/aaaa" maxLength={10} value={date}
                 onChange={(e) => setDate(e.target.value)} />
          {dateInvalid && <span className="field-error">Use o formato dd/mm/aaaa.</span>}
        </label>
      </div>
      <p className="note-desc" style={{ marginTop: 0 }}>
        {kind === "balance"
          ? "Informe o saldo atual — havendo um saldo anterior em OUTRA data, calculamos o rendimento entre as duas."
          : kind === "deposit"
          ? "Dinheiro novo que você colocou (não conta como rendimento)."
          : "Dinheiro que você sacou."}
      </p>
      {addEntry.isError && (
        <div className="banner banner-error">
          ⚠️ {addEntry.error instanceof ApiError ? addEntry.error.userMessage : "Erro ao lançar."}
        </div>
      )}
      <button className="primary" type="submit" disabled={addEntry.isPending || !(parseBRL(amount) > 0) || dateInvalid}>
        {addEntry.isPending ? "Salvando…" : "Salvar lançamento"}
      </button>
    </form>
  );
}

function AccountCard({ account, cdiAnnual }: { account: AccountSummary; cdiAnnual?: number | null }) {
  const archive = useArchiveAccount();
  const update = useUpdateAccount();
  const [open, setOpen] = useState(false);
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

  const rename = () => {
    const name = window.prompt("Novo nome da conta:", account.name);
    if (name && name.trim() && name.trim() !== account.name) {
      update.mutate({ id: account.id, body: { name: name.trim() } });
    }
  };

  return (
    <li className="card">
      <div className="reserve-card-head">
        <div className="card-id">
          <span className="card-ticker">
            {account.name}{" "}
            <button className="link-button reserve-rename" onClick={rename} aria-label={`Renomear ${account.name}`}>
              ✏️
            </button>
          </span>
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
          {open ? "▲ Fechar lançamento" : "＋ Lançar aporte / atualizar saldo"}
        </button>
        <button className="link-button" onClick={() => setShowEntries((v) => !v)}>
          {showEntries ? "▲ Ocultar lançamentos" : "📜 Ver lançamentos"}
        </button>
        <button
          className="link-button reserve-archive"
          onClick={() => {
            if (confirm(`Arquivar "${account.name}"? Os lançamentos ficam guardados e dá para desarquivar depois.`))
              archive.mutate(account.id);
          }}
          disabled={archive.isPending}
          aria-label={`Arquivar conta ${account.name} (reversível)`}
        >
          📦 Arquivar
        </button>
      </div>

      {open && <EntryForm account={account} onDone={() => setOpen(false)} />}
      {showEntries && <EntriesList accountId={account.id} />}

      {annual == null && (
        <p className="note-desc" style={{ padding: "0 14px 12px" }}>
          O rendimento aparece quando há um <strong>ponto de partida (aporte ou saldo) e um saldo
          atual em data posterior</strong>.{cdiAnnual != null ? ` CDI hoje: ${pct(cdiAnnual)} a.a.` : ""}
        </p>
      )}
    </li>
  );
}

function NewAccountForm() {
  const create = useCreateAccount();
  const addEntry = useAddEntry();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [institution, setInstitution] = useState("");
  const [kind, setKind] = useState("cdb");
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState(todayBR());

  const busy = create.isPending || addEntry.isPending;
  const dateInvalid = date.trim() !== "" && brToISO(date) === null;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim() || dateInvalid) return;
    const value = parseBRL(amount);
    create.mutate(
      { name: name.trim(), institution: institution.trim() || null, kind, benchmark: "cdi" },
      {
        onSuccess: (acc) => {
          // Se informou um saldo inicial, já registra como 1º "saldo" datado — assim a
          // PRÓXIMA atualização de saldo já calcula o rendimento (precisa de 2 datas).
          if (value > 0) {
            addEntry.mutate({ id: acc.id, body: { kind: "balance", amount: value, entry_date: brToISO(date) } });
          }
          setName(""); setInstitution(""); setAmount(""); setDate(todayBR()); setOpen(false);
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
      <div className="adv-row">
        <label className="field">
          <span>Saldo de partida (R$, opcional)</span>
          <input inputMode="decimal" placeholder="ex.: 10.000,00" value={amount} onChange={(e) => setAmount(e.target.value)} />
        </label>
        <label className="field">
          <span>Data desse saldo</span>
          <input inputMode="numeric" placeholder="dd/mm/aaaa" maxLength={10} value={date}
                 onChange={(e) => setDate(e.target.value)} />
          {dateInvalid && <span className="field-error">Use o formato dd/mm/aaaa.</span>}
        </label>
      </div>
      <p className="note-desc" style={{ marginTop: 0 }}>
        Dica: informe o saldo de partida com a <strong>data em que você aplicou</strong> (no passado).
        Depois, ao <strong>atualizar o saldo</strong> num outro dia, calculamos o rendimento entre as duas datas.
      </p>
      {(create.isError || addEntry.isError) && (
        <div className="banner banner-error">
          ⚠️ {create.error instanceof ApiError ? create.error.userMessage : "Erro ao criar a conta."}
        </div>
      )}
      <div className="reserve-actions">
        <button className="primary" type="submit" disabled={busy || !name.trim() || dateInvalid}>
          {busy ? "Criando…" : "Criar conta"}
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
  const update = useUpdateAccount();
  const [showArchived, setShowArchived] = useState(false);

  const accounts = (data?.accounts ?? []).filter((a) => !a.archived);
  const archived = (data?.accounts ?? []).filter((a) => a.archived);

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

      {data && <ReserveGoal totalReserve={data.total_balance} />}

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

      {archived.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <button className="link-button" onClick={() => setShowArchived((v) => !v)}>
            {showArchived ? "▲ Ocultar arquivadas" : `▼ Mostrar arquivadas (${archived.length})`}
          </button>
          {showArchived && (
            <ul className="cards" style={{ marginTop: 8 }}>
              {archived.map((a) => (
                <li key={a.id} className="card reserve-archived-row">
                  <div className="reserve-card-head">
                    <div className="card-id">
                      <span className="card-ticker">{a.name}</span>
                      <span className="card-name">arquivada · último saldo {money(a.current_balance)}</span>
                    </div>
                    <button
                      className="link-button"
                      disabled={update.isPending}
                      onClick={() => update.mutate({ id: a.id, body: { archived: false } })}
                    >
                      ↩ Desarquivar
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <p className="disclaimer">
        Rendimentos calculados a partir dos saldos que você informa. Não é recomendação de
        investimento.
      </p>
    </main>
  );
}
