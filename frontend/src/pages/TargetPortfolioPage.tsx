import { useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { usePortfolio, usePreferences, useSavePreferences, useWatchlist } from "../api/queries";
import { SavedToast } from "../components/SavedToast";
import { CLASS_LABEL, INVESTABLE_CLASSES } from "../lib/classes";
import type { Preferences } from "../types";

/** Percentuais com 2 casas: a composição é fina (22,08% e não "22%"). */
const toPct = (weight: number) => Math.round(weight * 10000) / 100;
const sumPct = (rows: Row[]) => rows.reduce((s, r) => s + (r.pct || 0), 0);
// Mesma tolerância do backend (0,1 p.p.): fora disso o PUT volta 422.
const sumOk = (rows: Row[]) => Math.abs(sumPct(rows) - 100) <= 0.1;

interface Row {
  ticker: string;
  pct: number;
}

/** Editor da composição de UMA classe: quais ativos e com que peso, somando 100%. */
function BasketEditor({
  cls,
  preferences,
  onSaved,
}: {
  cls: string;
  preferences?: Preferences;
  onSaved: () => void;
}) {
  const watchlist = useWatchlist();
  const portfolio = usePortfolio();
  const savePrefs = useSavePreferences();
  const [rows, setRows] = useState<Row[]>([]);
  const [newTicker, setNewTicker] = useState("");

  const saved = useMemo(() => preferences?.class_targets?.[cls] ?? {}, [preferences, cls]);

  useEffect(() => {
    setRows(Object.entries(saved).map(([t, w]) => ({ ticker: t, pct: toPct(w) })));
  }, [saved]);

  const label = CLASS_LABEL[cls] ?? cls;
  const suggestions = (watchlist.data?.items ?? [])
    .filter((i) => i.asset_class === cls && i.valid === 1)
    .map((i) => i.ticker)
    .filter((t) => !rows.some((r) => r.ticker === t));

  const addRow = () => {
    const t = newTicker.trim().toUpperCase();
    if (!t || rows.some((r) => r.ticker === t)) return;
    setRows((rs) => [...rs, { ticker: t, pct: 0 }]);
    setNewTicker("");
  };

  /** Semeia a composição com os pesos ATUAIS da carteira — ponto de partida honesto
   *  para quem já investe: começa de onde está e ajusta, em vez de digitar do zero. */
  const seedFromPortfolio = () => {
    const positions = (portfolio.data?.positions ?? []).filter((p) => p.asset_class === cls);
    const total = positions.reduce((s, p) => s + p.value, 0);
    if (!positions.length || total <= 0) return;
    const seeded = positions
      .map((p) => ({ ticker: p.ticker, pct: toPct(p.value / total) }))
      .sort((a, b) => b.pct - a.pct);
    // o arredondamento a 2 casas quase nunca fecha 100: a diferença vai para o maior peso
    const drift = Math.round((100 - sumPct(seeded)) * 100) / 100;
    if (seeded.length) seeded[0].pct = Math.round((seeded[0].pct + drift) * 100) / 100;
    setRows(seeded);
  };

  const distributeEvenly = () => {
    if (!rows.length) return;
    const even = Math.floor((100 / rows.length) * 100) / 100;
    const next = rows.map((r) => ({ ...r, pct: even }));
    next[0].pct = Math.round((next[0].pct + (100 - even * rows.length)) * 100) / 100;
    setRows(next);
  };

  const save = () => {
    const basket = Object.fromEntries(
      rows
        .filter((r) => r.ticker.trim())
        .map((r) => [r.ticker.trim().toUpperCase(), (r.pct || 0) / 100]),
    );
    savePrefs.mutate(
      { class_targets: { ...(preferences?.class_targets ?? {}), [cls]: basket } },
      { onSuccess: onSaved },
    );
  };

  const total = Math.round(sumPct(rows) * 100) / 100;
  const ok = sumOk(rows);
  const dirty =
    rows.length !== Object.keys(saved).length ||
    rows.some((r) => Math.abs((saved[r.ticker] ?? -1) * 100 - r.pct) > 0.001);

  return (
    <div className="basket-editor-body">
      <p className="muted">
        O peso é dentro de {label}, não da carteira inteira: some 100% aqui e a fatia de{" "}
        {label} continua sendo a meta da classe.
      </p>

      <div className="basket-rows">
        {rows.map((r, idx) => (
          <div className="basket-row" key={r.ticker}>
            <span className="card-ticker">{r.ticker}</span>
            <input
              type="number"
              min={0}
              max={100}
              step={0.01}
              value={r.pct}
              aria-label={`Peso de ${r.ticker} em ${label} (%)`}
              onChange={(e) =>
                setRows((rs) =>
                  rs.map((x, i) => (i === idx ? { ...x, pct: Number(e.target.value) } : x)),
                )
              }
            />
            <span className="muted">%</span>
            <button
              type="button"
              className="link-button"
              aria-label={`Remover ${r.ticker} da carteira alvo de ${label}`}
              onClick={() => setRows((rs) => rs.filter((_, i) => i !== idx))}
            >
              ✕
            </button>
          </div>
        ))}
        {rows.length === 0 && (
          <p className="muted">Nenhum ativo ainda — adicione o primeiro abaixo.</p>
        )}
      </div>

      <div className="basket-add">
        <input
          list={`basket-tickers-${cls}`}
          placeholder="Ticker (ex.: BBSE3)"
          value={newTicker}
          aria-label={`Ticker para adicionar à carteira alvo de ${label}`}
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
          ＋ adicionar
        </button>
      </div>

      <div className="basket-tools">
        <button type="button" className="link-button" onClick={seedFromPortfolio}>
          📥 Usar pesos atuais da carteira
        </button>
        <button
          type="button"
          className="link-button"
          onClick={distributeEvenly}
          disabled={rows.length === 0}
        >
          ⚖️ Dividir igualmente
        </button>
      </div>

      {rows.length > 0 && (
        <span className={`targets-sum ${ok ? "" : "warn"}`}>
          soma: {total}% {ok ? "✓" : "(deveria ser 100%)"}
        </span>
      )}

      <button
        type="button"
        className="primary"
        onClick={save}
        disabled={savePrefs.isPending || (rows.length > 0 && !ok) || !dirty}
      >
        {savePrefs.isPending
          ? "Salvando…"
          : rows.length === 0 && Object.keys(saved).length > 0
            ? "💾 Salvar (remove a composição desta classe)"
            : `💾 Salvar composição de ${label}`}
      </button>
    </div>
  );
}

/** Metas de alocação POR CLASSE (a fatia de cada tipo na carteira inteira). */
function ClassTargetsEditor({
  preferences,
  onSaved,
}: {
  preferences?: Preferences;
  onSaved: () => void;
}) {
  const savePrefs = useSavePreferences();
  const [pct, setPct] = useState<Record<string, number>>({});

  useEffect(() => {
    if (!preferences) return;
    setPct(
      Object.fromEntries(
        INVESTABLE_CLASSES.map((c) => [c, Math.round((preferences.targets?.[c] ?? 0) * 100)]),
      ),
    );
  }, [preferences]);

  const total = Object.values(pct).reduce((s, v) => s + (v || 0), 0);
  const ok = Math.abs(total - 100) <= 0.5;

  return (
    <section className="card target-classes">
      <h2>Metas por classe</h2>
      <p className="muted">
        Quanto da carteira cada tipo de ativo deve representar. É o primeiro nível da decisão;
        a composição de cada classe vem abaixo.
      </p>
      <div className="adv-row">
        {INVESTABLE_CLASSES.map((cls) => (
          <label className="field" key={cls}>
            <span>{CLASS_LABEL[cls]}</span>
            <input
              type="number"
              min={0}
              max={100}
              value={pct[cls] ?? 0}
              onChange={(e) => setPct((t) => ({ ...t, [cls]: Number(e.target.value) }))}
            />
          </label>
        ))}
      </div>
      <span className={`targets-sum ${ok ? "" : "warn"}`}>
        soma: {total}% {ok ? "✓" : "(deveria ser 100%)"}
      </span>
      <button
        type="button"
        className="link-button"
        disabled={!ok || savePrefs.isPending}
        onClick={() =>
          savePrefs.mutate(
            {
              targets: Object.fromEntries(
                Object.entries(pct).map(([k, v]) => [k, (v || 0) / 100]),
              ),
            },
            { onSuccess: onSaved },
          )
        }
      >
        {savePrefs.isPending ? "Salvando…" : "💾 Salvar metas por classe"}
      </button>
    </section>
  );
}

export function TargetPortfolioPage() {
  const preferences = usePreferences();
  const { hash } = useLocation();
  const [open, setOpen] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<number | null>(null);

  // Deep-link /alvo#FII abre a classe já expandida (vem dos avisos do plano).
  useEffect(() => {
    const cls = hash.replace("#", "").toUpperCase();
    if (INVESTABLE_CLASSES.includes(cls as never)) setOpen(cls);
  }, [hash]);

  const prefs = preferences.data;
  const onSaved = () => setSavedAt(Date.now());

  return (
    <main className="page">
      <SavedToast show={savedAt} message="Carteira alvo salva." />
      <h1 className="page-title">🎯 Carteira alvo</h1>
      <p className="muted">
        É daqui que sai toda recomendação do Plantar: o aporte vai para quem está mais longe
        do peso que você definiu. <Link to="/plano">Voltar ao Plantar →</Link>
      </p>

      {preferences.isLoading && <p className="muted">Carregando…</p>}

      {prefs && (
        <>
          <ClassTargetsEditor preferences={prefs} onSaved={onSaved} />

          <h2 className="section-title">Composição de cada classe</h2>
          <ul className="cards">
            {INVESTABLE_CLASSES.map((cls) => {
              const basket = prefs.class_targets?.[cls] ?? {};
              const n = Object.keys(basket).length;
              const sum = Object.values(basket).reduce((s, w) => s + w, 0);
              const isOpen = open === cls;
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
                          ? `${n} ativo${n > 1 ? "s" : ""} · soma ${Math.round(sum * 10000) / 100}%` +
                            (Math.abs(sum - 1) <= 0.001 ? " ✓" : " ⚠")
                          : "sem composição"}
                      </span>
                    </span>
                    <span className="card-toggle">{isOpen ? "▲" : "▼"}</span>
                  </button>
                  {isOpen && <BasketEditor cls={cls} preferences={prefs} onSaved={onSaved} />}
                </li>
              );
            })}
          </ul>
        </>
      )}
    </main>
  );
}
