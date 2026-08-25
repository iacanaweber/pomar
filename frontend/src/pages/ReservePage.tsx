import { useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ApiError } from "../api/client";
import {
  useAddEntry,
  useArchiveAccount,
  useAssignments,
  useCreateAccount,
  useDeleteEntry,
  useEntries,
  useFixedIncome,
  useLabels,
  usePreferences,
  useSavePreferences,
  useSetAssignments,
  useUpdateAccount,
} from "../api/queries";
import type {
  AccountSummary,
  AssignmentOut,
  FloorStatus,
  Liquidity,
  NewLiquidity,
  Purpose,
} from "../types";
import { brToISO, isoToBR, money, parseBRL, pct, todayBR } from "../lib/format";
import { Tooltip } from "../components/Tooltip";

/** Piso da reserva: o mínimo que fica em renda fixa de RESGATE IMEDIATO.
 *
 *  Não é uma reserva separada da carteira — é um piso dentro da própria classe de renda
 *  fixa, então o mesmo dinheiro nunca aparece duas vezes no patrimônio. Aplicação travada
 *  soma no peso da classe e não conta aqui: o piso mede o que está disponível hoje.
 */
function ReserveFloorCard({ floor }: { floor: FloorStatus | null | undefined }) {
  const prefs = usePreferences();
  const savePrefs = useSavePreferences();
  const [editing, setEditing] = useState(false);
  const [amount, setAmount] = useState("");
  const [index, setIndex] = useState<"none" | "ipca">("none");
  const [date, setDate] = useState(todayBR());

  const dateInvalid = date.trim() !== "" && brToISO(date) === null;

  const open = () => {
    const saved = prefs.data;
    setAmount(saved?.reserve_floor_amount ? String(saved.reserve_floor_amount).replace(".", ",") : "");
    setIndex(saved?.reserve_floor_index ?? "none");
    setDate(saved?.reserve_floor_date ? isoToBR(saved.reserve_floor_date) : todayBR());
    setEditing(true);
  };

  const save = () => {
    const value = parseBRL(amount);
    if (!(value >= 0) || dateInvalid) return;
    savePrefs.mutate(
      {
        reserve_floor_amount: value,
        reserve_floor_index: index,
        reserve_floor_date: index === "ipca" ? brToISO(date) : null,
      },
      { onSuccess: () => setEditing(false) },
    );
  };

  if (editing) {
    return (
      <form
        className="controls reserve-goal"
        onSubmit={(e) => {
          e.preventDefault();
          save();
        }}
      >
        <label className="field">
          <span>Piso da reserva (R$)</span>
          <div className="money">
            <span>R$</span>
            <input
              inputMode="decimal"
              placeholder="ex.: 30.000,00"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              autoFocus
            />
          </div>
        </label>
        <div className="adv-row">
          <label className="field">
            <span>Correção</span>
            <select value={index} onChange={(e) => setIndex(e.target.value as "none" | "ipca")}>
              <option value="none">Nenhuma (valor nominal)</option>
              <option value="ipca">IPCA a partir da data-base</option>
            </select>
          </label>
          {index === "ipca" && (
            <label className="field">
              <span>Data-base</span>
              <input
                inputMode="numeric"
                placeholder="dd/mm/aaaa"
                maxLength={10}
                value={date}
                onChange={(e) => setDate(e.target.value)}
              />
              {dateInvalid && <span className="field-error">Use o formato dd/mm/aaaa.</span>}
            </label>
          )}
        </div>
        {index === "ipca" && (
          <p className="note-desc" style={{ marginTop: 0 }}>
            Com a correção ligada, o piso sobe alguns reais por mês e o plano pede aportes
            residuais na renda fixa de tempos em tempos.
          </p>
        )}
        <div className="reserve-actions">
          <button className="primary" type="submit" disabled={savePrefs.isPending || dateInvalid}>
            {savePrefs.isPending ? "Salvando…" : "Salvar piso"}
          </button>
          <button className="link-button" type="button" onClick={() => setEditing(false)}>
            Cancelar
          </button>
        </div>
      </form>
    );
  }

  if (!floor || floor.floor_nominal <= 0) {
    return (
      <div className="alloc reserve-goal">
        <p className="muted" style={{ margin: 0 }}>
          Sem piso definido — nenhum aporte é desviado para a renda fixa.
        </p>
        <button className="link-button" onClick={open}>
          Definir piso da reserva
        </button>
      </div>
    );
  }

  const filled = Math.round(floor.pct_filled * 100);
  const corrigido = floor.index === "ipca" && floor.index_available;

  return (
    <div className="alloc reserve-goal">
      <div className="goal-head">
        <Tooltip metricKey="reserve_floor">
          <h3 style={{ margin: 0 }}>Piso da reserva</h3>
        </Tooltip>
        <button className="link-button" onClick={open}>
          editar
        </button>
      </div>
      <div
        className="goal-bar"
        role="progressbar"
        aria-valuenow={filled}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Reserva líquida: ${filled}% do piso`}
      >
        <div className="alloc-track" style={{ height: 18 }}>
          <div
            className="alloc-cur"
            style={{
              width: `${Math.min(100, filled)}%`,
              background: filled >= 100 ? "var(--green)" : "var(--leaf)",
            }}
          />
        </div>
        <span className="goal-bar-label">{filled}% do piso</span>
      </div>
      <p className="goal-status" style={{ marginBottom: 0 }}>
        Piso <strong>{money(floor.floor_corrected)}</strong> · reserva líquida{" "}
        <strong>{money(floor.liquid_reserve)}</strong>
        {floor.deficit > 0 ? (
          <> · faltam <strong>{money(floor.deficit)}</strong></>
        ) : (
          <> · ✅ cumprido</>
        )}
      </p>
      {corrigido && (
        <p className="muted" style={{ fontSize: 12, margin: 0 }}>
          Nominal {money(floor.floor_nominal)}, corrigido pelo IPCA desde{" "}
          {floor.floor_date ? isoToBR(floor.floor_date) : "—"}.
        </p>
      )}
      {floor.index === "ipca" && !floor.index_available && (
        <p className="muted" style={{ fontSize: 12, margin: 0 }}>
          Correção do IPCA indisponível agora — exibindo o piso nominal.
        </p>
      )}
      <p className="muted" style={{ fontSize: 12, margin: 0 }}>
        Só entra aqui o que tem resgate imediato e conta na carteira.
      </p>
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

const PURPOSE_LABEL: Record<string, string> = {
  investment: "Investimento",
  earmarked: "Reservado para outro fim",
};

const LIQUIDITY_LABEL: Record<string, string> = {
  immediate: "Resgate imediato",
  scheduled: "Janela ou vencimento",
  locked: "Carência",
  unknown: "Liquidez não informada",
};

/** Como a conta participa da carteira: se conta, para que serve e em quanto tempo o
 *  dinheiro está na mão — mais a tag de indexador, que é o item dela na cesta de renda
 *  fixa. São as três perguntas que decidem em que somas ela entra. */
function AccountClassification({
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
          {open ? "▲ fechar" : "editar"}
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
          {update.isError && (
            <div className="banner banner-error">
              ⚠️{" "}
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

function AccountCard({
  account,
  cdiAnnual,
  tag,
  autoOpen = false,
}: {
  account: AccountSummary;
  cdiAnnual?: number | null;
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
          <span>Liquidez</span>
          <select
            value={liquidity}
            onChange={(e) => setLiquidity(e.target.value as NewLiquidity)}
          >
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

const AVISO_MARCAR = "pomar:reserva-aviso-marcar";

export function ReservePage() {
  const navigate = useNavigate();
  // Atalho do Plantar (/reserva?conta=7): abre a conta sugerida já no lançamento, para o
  // usuário não ter que reencontrá-la e redigitar o que o plano acabou de dizer.
  const [params] = useSearchParams();
  const contaDoAtalho = Number(params.get("conta")) || null;
  const { data, isLoading, error } = useFixedIncome();
  const update = useUpdateAccount();
  const tags = useAssignments({ dimension: "indexer", subjectType: "fi_account" });
  const [showArchived, setShowArchived] = useState(false);
  const [avisoLido, setAvisoLido] = useState(() => !!localStorage.getItem(AVISO_MARCAR));

  const accounts = (data?.accounts ?? []).filter((a) => !a.archived);
  const archived = (data?.accounts ?? []).filter((a) => a.archived);
  const tagOf = new Map((tags.data ?? []).map((t) => [t.subject_id, t]));
  // Contas antigas nasceram fora da carteira (default deliberado): um aviso de uma linha,
  // dispensável, em vez de mudar o comportamento delas por conta própria.
  const precisaMarcar = accounts.length > 0 && accounts.every((a) => !a.counts_in_portfolio);

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
          <span className="muted">Total em renda fixa</span>
          <strong className="pf-total">{money(data.total_balance)}</strong>
          <div className="reserve-totals">
            <span>
              Conta na carteira <strong>{money(data.portfolio_balance)}</strong>
            </span>
            <span>
              <Tooltip metricKey="liquid_reserve">
                <span>Reserva líquida</span>
              </Tooltip>{" "}
              <strong>{money(data.liquid_balance)}</strong>
            </span>
            {data.excluded_balance > 0 && (
              <span>
                Fora da carteira <strong>{money(data.excluded_balance)}</strong>
              </span>
            )}
          </div>
          {data.cdi_annual != null && (
            <span className="muted">CDI de referência: {pct(data.cdi_annual)} a.a.</span>
          )}
        </div>
      )}

      {data && <ReserveFloorCard floor={data.floor} />}

      {data && accounts.length === 0 && (
        <div className="banner banner-warn">
          Nenhuma aplicação ainda. Adicione sua reserva (conta, CDB, Tesouro) para acompanhar o
          rendimento e comparar com o CDI.
        </div>
      )}

      {precisaMarcar && !avisoLido && (
        <p className="banner radar-banner">
          Marque em cada conta se ela conta no patrimônio — nenhuma conta antiga passou a
          contar sozinha.{" "}
          <button
            className="link-button"
            onClick={() => {
              localStorage.setItem(AVISO_MARCAR, "1");
              setAvisoLido(true);
            }}
          >
            ok, entendi
          </button>
        </p>
      )}

      {accounts.length > 0 && (
        <ul className="cards" style={{ marginBottom: 16 }}>
          {accounts.map((a) => (
            <AccountCard
              key={a.id}
              account={a}
              cdiAnnual={data?.cdi_annual}
              tag={tagOf.get(String(a.id))}
              autoOpen={a.id === contaDoAtalho}
            />
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
