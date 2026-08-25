import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  useIndexers,
  useLabels,
  usePortfolio,
  usePreferences,
  useSavePreferences,
  useWatchlist,
} from "../api/queries";
import { SavedToast } from "../components/SavedToast";
import { TargetPortfolioChart } from "../components/TargetPortfolioChart";
import {
  applySnap,
  distributeEvenly,
  fromCurrentValues,
  round2,
  scaleTo100,
  snapPointFor,
  sumPct,
  sumState,
  type Row,
  type SumState,
} from "../lib/basket";
import { ALLOCATION_CLASSES, byWeightDesc, CLASS_LABEL, RENDA_FIXA } from "../lib/classes";
import { parseBRL } from "../lib/format";
import { Icon } from "../components/Icon";

const fmtPct = (n: number) => n.toFixed(2).replace(".", ",");
const SUM_CLASS: Record<SumState, string> = { over: "sum-over", under: "sum-under", ok: "sum-ok" };

/** Uma linha do editor: ticker, slider e campo — os três amarrados ao mesmo peso. */
function WeightRow({
  row,
  label,
  state,
  snap,
  onChange,
  onRemove,
}: {
  row: Row;
  label: string;
  state: SumState;
  /** Valor que fecha os 100% neste slider — vira marca visual e destino magnético. */
  snap: number | null;
  onChange: (pct: number) => void;
  onRemove: () => void;
}) {
  // O campo tem estado próprio enquanto está sendo digitado: normalizar a cada tecla
  // impediria de apagar para redigitar ("2" → "" → "21,23").
  const [draft, setDraft] = useState<string | null>(null);
  const shown = draft ?? fmtPct(row.pct);

  const commit = (text: string) => {
    const n = parseBRL(text);
    onChange(Number.isFinite(n) ? Math.min(100, Math.max(0, round2(n))) : 0);
    setDraft(null);
  };

  return (
    <div className="weight-row">
      <span className="weight-ticker">{row.ticker}</span>
      <div className="weight-slider-wrap">
        <input
          className={`weight-slider ${SUM_CLASS[state]}`}
          type="range"
          min={0}
          max={100}
          step={0.01}
          value={row.pct}
          // a marca é aria-hidden (é decoração visual), então o valor que fecha os 100%
          // entra aqui — é o rótulo que o leitor de tela realmente anuncia
          aria-label={
            snap == null
              ? `Peso de ${row.ticker} em ${label}`
              : `Peso de ${row.ticker} em ${label} — fecha 100% em ${fmtPct(snap)}%`
          }
          onChange={(e) => {
            setDraft(null);
            // gruda no ponto que fecha 100% quando o arraste passa perto dele
            onChange(applySnap(Number(e.target.value), snap));
          }}
        />
        {snap != null && (
          <span
            className={`weight-snap ${SUM_CLASS[state]}`}
            style={{ left: `calc(${snap} * (100% - var(--thumb)) / 100 + var(--thumb) / 2)` }}
            title={`Fecha 100% em ${fmtPct(snap)}%`}
            aria-hidden="true"
          />
        )}
      </div>
      <input
        className="weight-input"
        inputMode="decimal"
        value={shown}
        aria-label={`Peso de ${row.ticker} em ${label}, em porcento`}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={(e) => commit(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            commit((e.target as HTMLInputElement).value);
          }
        }}
      />
      <span className="muted">%</span>
      <button
        type="button"
        className="link-button weight-remove"
        aria-label={`Remover ${row.ticker} da carteira alvo de ${label}`}
        onClick={onRemove}
      >
        ✕
      </button>
    </div>
  );
}

/** Editor da composição de UMA classe. Controlado: o rascunho vive na página, porque o
 *  gráfico do topo precisa refletir a edição ANTES de salvar. */
function BasketEditor({
  cls,
  rows,
  saved,
  onChange,
  onSaved,
}: {
  cls: string;
  rows: Row[];
  saved: Record<string, number>;
  onChange: (rows: Row[]) => void;
  onSaved: () => void;
}) {
  const watchlist = useWatchlist();
  const portfolio = usePortfolio();
  const savePrefs = useSavePreferences();
  const preferences = usePreferences();
  // Em renda fixa o item da cesta é uma TAG DE INDEXADOR (CDI, IPCA, LCI…), não um ticker:
  // mesma aritmética de pesos, outro tipo de item — e outra lista de sugestões.
  const isRF = cls === RENDA_FIXA;
  const indexerLabels = useLabels("indexer");
  const indexers = useIndexers();
  const [newTicker, setNewTicker] = useState("");

  const label = CLASS_LABEL[cls] ?? cls;
  const suggestions = isRF
    ? (indexerLabels.data ?? [])
        .map((l) => l.code)
        .filter((code) => !rows.some((r) => r.ticker === code))
    : (watchlist.data?.items ?? [])
        .filter((i) => i.asset_class === cls && i.valid === 1)
        .map((i) => i.ticker)
        .filter((t) => !rows.some((r) => r.ticker === t));

  const total = sumPct(rows);
  const state = sumState(rows);
  const ok = state === "ok";
  const dirty =
    rows.length !== Object.keys(saved).length ||
    rows.some((r) => Math.abs((saved[r.ticker] ?? -1) * 100 - r.pct) > 0.001);

  const addRow = () => {
    const t = newTicker.trim().toUpperCase();
    if (!t || rows.some((r) => r.ticker === t)) return;
    onChange([...rows, { ticker: t, pct: 0 }]); // entra com 0%: o peso é decisão consciente
    setNewTicker("");
  };

  /** Semeia a composição com os pesos ATUAIS da carteira — ponto de partida honesto para
   *  quem já investe: começa de onde está e ajusta, em vez de digitar do zero.
   *  Em renda fixa a "posição atual" é o valor por indexador (contas + ativos atribuídos). */
  const seedFromPortfolio = () => {
    const atual = isRF
      ? (indexers.data?.items ?? [])
          .filter((i) => i.value > 0)
          .map((i) => ({ ticker: i.code, value: i.value }))
      : (portfolio.data?.positions ?? [])
          .filter((p) => p.asset_class === cls)
          .map((p) => ({ ticker: p.ticker, value: p.value }));
    const seeded = fromCurrentValues(atual);
    if (seeded.length) onChange(seeded);
  };

  const save = () => {
    const basket = Object.fromEntries(
      rows.filter((r) => r.ticker.trim()).map((r) => [r.ticker, (r.pct || 0) / 100]),
    );
    savePrefs.mutate(
      { class_targets: { ...(preferences.data?.class_targets ?? {}), [cls]: basket } },
      { onSuccess: onSaved },
    );
  };

  return (
    <div className="basket-editor-body">
      <p className="muted">
        O peso é dentro de {label}: some 100% aqui e a fatia de {label} continua sendo a meta
        da classe. O gráfico no topo mostra quanto isso vale sobre a carteira inteira.
        {isRF && " Aqui os itens são indexadores, e a compra é feita fora do app."}
      </p>

      <div className="basket-rows">
        {rows.map((r, idx) => (
          <WeightRow
            key={r.ticker}
            row={r}
            label={label}
            state={state}
            snap={snapPointFor(rows, idx)}
            onChange={(pct) => onChange(rows.map((x, i) => (i === idx ? { ...x, pct } : x)))}
            onRemove={() => onChange(rows.filter((_, i) => i !== idx))}
          />
        ))}
        {rows.length === 0 && (
          <p className="muted">
            {isRF ? "Nenhum indexador ainda" : "Nenhum ativo ainda"} — adicione o primeiro abaixo.
          </p>
        )}
      </div>

      <div className="basket-add">
        <input
          list={`basket-tickers-${cls}`}
          inputMode="text"
          placeholder={isRF ? "Indexador (ex.: CDI)" : "Ticker (ex.: PETR4)"}
          value={newTicker}
          aria-label={
            isRF
              ? `Indexador para adicionar à carteira alvo de ${label}`
              : `Ticker para adicionar à carteira alvo de ${label}`
          }
          onChange={(e) => setNewTicker(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              addRow();
            }
          }}
        />
        <datalist id={`basket-tickers-${cls}`}>
          {suggestions.map((t) => (
            <option key={t} value={t} />
          ))}
        </datalist>
        <button type="button" className="link-button" onClick={addRow} disabled={!newTicker.trim()}>
          adicionar
        </button>
      </div>

      {rows.length > 0 && (
        <div className={`basket-sum ${SUM_CLASS[state]}`}>
          <span className="basket-sum-value">soma: {fmtPct(total)}%</span>
          <span className="basket-sum-note">
            {state === "ok"
              ? "✓ fechado"
              : state === "over"
                ? `passou ${fmtPct(round2(total - 100))} p.p. — precisa fechar em 100%`
                : `faltam ${fmtPct(round2(100 - total))} p.p. — precisa fechar em 100%`}
          </span>
          {!ok && (
            <button type="button" className="link-button" onClick={() => onChange(scaleTo100(rows))}>
              Ajustar para 100%
            </button>
          )}
        </div>
      )}

      <div className="basket-tools">
        <button type="button" className="link-button" onClick={seedFromPortfolio}>
          {isRF ? "Usar o que já está aplicado" : "Usar pesos atuais da carteira"}
        </button>
        <button
          type="button"
          className="link-button"
          onClick={() => onChange(distributeEvenly(rows))}
          disabled={rows.length === 0}
        >
          Dividir igualmente
        </button>
      </div>

      <button
        type="button"
        className="primary"
        onClick={save}
        disabled={savePrefs.isPending || (rows.length > 0 && !ok) || !dirty}
      >
        {savePrefs.isPending
          ? "Salvando…"
          : rows.length === 0 && Object.keys(saved).length > 0
            ? "Salvar (remove a composição desta classe)"
            : `Salvar composição de ${label}`}
      </button>
    </div>
  );
}

/** Metas de alocação POR CLASSE (a fatia de cada tipo na carteira inteira). */
function ClassTargetsEditor({
  pct,
  onChange,
  onSaved,
}: {
  pct: Record<string, number>;
  onChange: (pct: Record<string, number>) => void;
  onSaved: () => void;
}) {
  const savePrefs = useSavePreferences();
  const rows: Row[] = ALLOCATION_CLASSES.map((c) => ({ ticker: c, pct: pct[c] ?? 0 }));
  const total = sumPct(rows);
  const state = sumState(rows);

  return (
    <section className="card target-classes">
      <h2>Metas por classe</h2>
      <p className="muted">
        Quanto da carteira cada tipo de ativo deve representar. É o primeiro nível da decisão;
        a composição de cada classe vem abaixo.
      </p>
      <div className="adv-row">
        {ALLOCATION_CLASSES.map((cls) => (
          <label className="field" key={cls}>
            <span>{CLASS_LABEL[cls]}</span>
            <input
              type="number"
              inputMode="decimal"
              min={0}
              max={100}
              step={1}
              value={pct[cls] ?? 0}
              onChange={(e) => onChange({ ...pct, [cls]: round2(Number(e.target.value)) })}
            />
          </label>
        ))}
      </div>
      <div className={`basket-sum ${SUM_CLASS[state]}`}>
        <span className="basket-sum-value">soma: {fmtPct(total)}%</span>
        <span className="basket-sum-note">
          {state === "ok" ? "✓ fechado" : "precisa fechar em 100%"}
        </span>
        {state !== "ok" && (
          <button
            type="button"
            className="link-button"
            onClick={() =>
              onChange(Object.fromEntries(scaleTo100(rows).map((r) => [r.ticker, r.pct])))
            }
          >
            Ajustar para 100%
          </button>
        )}
      </div>
      <button
        type="button"
        className="link-button"
        disabled={state !== "ok" || savePrefs.isPending}
        onClick={() =>
          savePrefs.mutate(
            { targets: Object.fromEntries(rows.map((r) => [r.ticker, r.pct / 100])) },
            { onSuccess: onSaved },
          )
        }
      >
        {savePrefs.isPending ? "Salvando…" : "Salvar metas por classe"}
      </button>
    </section>
  );
}

export function TargetPortfolioPage() {
  const preferences = usePreferences();
  const { hash } = useLocation();
  const [open, setOpen] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<number | null>(null);

  // Rascunhos vivem AQUI (e não em cada editor) porque o gráfico do topo precisa mostrar
  // a edição antes de salvar. `null` = ainda não editado nesta sessão: segue o servidor.
  const [classPct, setClassPct] = useState<Record<string, number> | null>(null);
  const [drafts, setDrafts] = useState<Record<string, Row[]>>({});

  const prefs = preferences.data;
  const savedBaskets = useMemo(() => prefs?.class_targets ?? {}, [prefs]);

  const savedClassPct = useMemo(
    () =>
      Object.fromEntries(
        ALLOCATION_CLASSES.map((c) => [c, round2((prefs?.targets?.[c] ?? 0) * 100)]),
      ),
    [prefs],
  );

  const savedRows = useCallback(
    (cls: string): Row[] =>
      Object.entries(savedBaskets[cls] ?? {}).map(([ticker, w]) => ({
        ticker,
        pct: round2(w * 100),
      })),
    [savedBaskets],
  );

  // Deep-link /alvo#FII abre a classe já expandida (vem dos avisos do plano).
  useEffect(() => {
    const cls = hash.replace("#", "").toUpperCase();
    if (ALLOCATION_CLASSES.includes(cls as never)) setOpen(cls);
  }, [hash]);

  const effectivePct = classPct ?? savedClassPct;
  const rowsOf = (cls: string): Row[] => drafts[cls] ?? savedRows(cls);

  /** Depois de salvar, o rascunho daquela classe é descartado: o servidor volta a mandar. */
  const onSavedClass = (cls?: string) => {
    setSavedAt(Date.now());
    if (cls) {
      setDrafts((d) => {
        const { [cls]: _discarded, ...rest } = d;
        return rest;
      });
    } else {
      setClassPct(null);
    }
  };

  // Ordem de LEITURA: o que pesa mais vem antes. Derivada do valor SALVO, e não do
  // rascunho — ordenar pelo que está sendo digitado faria a barra pular embaixo do dedo a
  // cada dígito. Reordena só ao salvar. O gráfico e a lista abaixo usam a MESMA ordem.
  const readOrder = useMemo(
    () => byWeightDesc(ALLOCATION_CLASSES, (c) => savedClassPct[c] ?? 0),
    [savedClassPct],
  );

  const chartData = readOrder.map((cls) => ({
    cls,
    classPct: effectivePct[cls] ?? 0,
    rows: rowsOf(cls),
  }));

  return (
    <main className="page">
      <SavedToast show={savedAt} message="Carteira alvo salva." />
      <h1 className="page-title">Carteira alvo</h1>
      <p className="muted">
        É daqui que sai toda recomendação do Plantar: o aporte vai para quem está mais longe
        do peso que você definiu. <Link to="/plano">Voltar ao Plantar →</Link>
      </p>

      {preferences.isLoading && <p className="muted">Carregando…</p>}

      {prefs && (
        <>
          <TargetPortfolioChart classes={chartData} />

          <ClassTargetsEditor
            pct={effectivePct}
            onChange={setClassPct}
            onSaved={() => onSavedClass()}
          />

          <h2 className="section-title">Composição de cada classe</h2>
          <ul className="cards">
            {readOrder.map((cls) => {
              const rows = rowsOf(cls);
              const n = rows.length;
              const sum = sumPct(rows);
              const isOpen = open === cls;
              const closed = Math.abs(sum - 100) <= 0.1;
              return (
                <li className="card" key={cls} id={cls}>
                  <button
                    className="basket-head"
                    onClick={() => setOpen(isOpen ? null : cls)}
                    aria-expanded={isOpen}
                  >
                    <span className="card-id">
                      <span className="card-ticker">{CLASS_LABEL[cls]}</span>
                      <span className="card-name">
                        {n > 0
                          ? `${n} ativo${n > 1 ? "s" : ""} · soma ${fmtPct(sum)}%${closed ? " ✓" : " ⚠"}`
                          : "sem composição"}
                      </span>
                    </span>
                    <span className="card-toggle"><Icon name="chevron" size={16} /></span>
                  </button>
                  {isOpen && (
                    <BasketEditor
                      cls={cls}
                      rows={rows}
                      saved={savedBaskets[cls] ?? {}}
                      onChange={(next) => setDrafts((d) => ({ ...d, [cls]: next }))}
                      onSaved={() => onSavedClass(cls)}
                    />
                  )}
                </li>
              );
            })}
          </ul>
        </>
      )}
    </main>
  );
}
