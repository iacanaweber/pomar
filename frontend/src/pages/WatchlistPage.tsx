import { useState, type FormEvent } from "react";
import { ApiError } from "../api/client";
import { useAddWatchlist, useRemoveWatchlist, useWatchlist } from "../api/queries";
import { AssetLink } from "../components/AssetLink";
import type { WatchlistItem } from "../types";
import { shortDateTime } from "../lib/format";

function StatusChip({ item }: { item: WatchlistItem }) {
  if (item.valid === 1)
    return (
      <span className="ceiling-chip risk-verde" aria-label="ticker validado">
        <span aria-hidden="true">✓</span>
        <span>validado{item.last_validated_at ? ` ${shortDateTime(item.last_validated_at)}` : ""}</span>
      </span>
    );
  if (item.valid === 0 && item.last_validated_at)
    return (
      <span className="ceiling-chip risk-vermelho" aria-label="ticker não encontrado">
        <span aria-hidden="true">⚠</span>
        <span>não encontrado</span>
      </span>
    );
  return (
    <span className="ceiling-chip metric-na" aria-label="validando">
      <span aria-hidden="true">⏳</span>
      <span>validando…</span>
    </span>
  );
}

function WatchlistRow({ item }: { item: WatchlistItem }) {
  const remove = useRemoveWatchlist();
  return (
    <li className="card watchlist-row">
      <div className="watchlist-main">
        <div className="card-id">
          <span className="card-ticker"><AssetLink ticker={item.ticker} /></span>
          <span className="card-name">{item.asset_class || "—"}</span>
        </div>
        <StatusChip item={item} />
      </div>
      <div className="watchlist-actions">
        <AssetLink ticker={item.ticker}>ver detalhes →</AssetLink>
        <button
          className="link-button watchlist-remove"
          onClick={() => remove.mutate(item.ticker)}
          disabled={remove.isPending}
          aria-label={`Remover ${item.ticker} da lista`}
        >
          🗑
        </button>
      </div>
    </li>
  );
}

export function WatchlistPage() {
  const { data, isLoading } = useWatchlist();
  const add = useAddWatchlist();
  const [ticker, setTicker] = useState("");

  const items = data?.items ?? [];

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const t = ticker.trim().toUpperCase();
    if (!t) return;
    if (items.some((i) => i.ticker.toUpperCase() === t)) return;
    add.mutate({ ticker: t }, { onSuccess: () => setTicker("") });
  };

  const duplicate = items.some((i) => i.ticker.toUpperCase() === ticker.trim().toUpperCase()) && ticker.trim() !== "";

  return (
    <main className="page">
      <h2>Observando</h2>
      <p className="muted" style={{ marginTop: 0 }}>
        Adicione ativos que você quer acompanhar antes de comprar.
      </p>

      <form className="watchlist-add" onSubmit={submit}>
        <input
          placeholder="Ticker (ex.: PETR4)"
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          aria-label="Ticker para adicionar"
        />
        <button className="primary" type="submit" disabled={add.isPending || !ticker.trim() || duplicate}>
          {add.isPending ? "Adicionando…" : "＋ Adicionar"}
        </button>
      </form>
      {duplicate && <p className="field-error">{ticker.trim().toUpperCase()} já está na sua lista.</p>}
      {add.isError && (
        <div className="banner banner-error">
          ⚠️ {add.error instanceof ApiError ? add.error.userMessage : "Não consegui adicionar."}
        </div>
      )}

      {isLoading && <p className="muted">Carregando sua lista…</p>}

      {!isLoading && items.length === 0 && (
        <div className="banner banner-warn">
          Sua lista está vazia. Adicione ativos que você quer observar.
        </div>
      )}

      {items.length > 0 && (
        <ul className="cards">
          {items.map((i) => (
            <WatchlistRow key={i.ticker} item={i} />
          ))}
        </ul>
      )}

      <p className="disclaimer">Conteúdo educativo. Não é recomendação de investimento.</p>
    </main>
  );
}
