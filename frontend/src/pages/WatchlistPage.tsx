import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/client";
import { useAddWatchlist, useRemoveWatchlist, useWatchlist, useWatchlistRadar } from "../api/queries";
import { AssetLink } from "../components/AssetLink";
import { CeilingBadge } from "../components/CeilingBadge";
import type { RadarItem, WatchlistItem } from "../types";
import { money, pct, shortDateTime } from "../lib/format";
import { Icon } from "../components/Icon";

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
      <span>Validando</span>
    </span>
  );
}

function WatchlistRow({ item, radar }: { item: WatchlistItem; radar?: RadarItem }) {
  const remove = useRemoveWatchlist();
  return (
    <li className="card watchlist-row">
      <div className="watchlist-main">
        <div className="card-id">
          <span className="card-ticker">
            <AssetLink ticker={item.ticker} />
            {radar?.in_portfolio && <span className="muted watchlist-own"> · já tenho</span>}
          </span>
          <span className="card-name">{item.asset_class || "—"}</span>
        </div>
        {radar ? (
          <div className="watchlist-radar-data">
            <span className="muted">
              {radar.price != null ? money(radar.price) : "—"}
              {radar.dividend_yield != null && <> · DY {pct(radar.dividend_yield)}</>}
              {radar.ceiling_price != null && <> · teto {money(radar.ceiling_price)}</>}
            </span>
            <CeilingBadge
              ceiling={radar.ceiling_price}
              price={radar.price}
              margin={radar.margin}
              belowCeiling={radar.below_ceiling}
              variant="chip"
            />
          </div>
        ) : (
          <StatusChip item={item} />
        )}
      </div>
      <div className="watchlist-actions">
        <AssetLink ticker={item.ticker}>ver detalhes →</AssetLink>
        <button
          className="link-button watchlist-remove"
          onClick={() => remove.mutate(item.ticker)}
          disabled={remove.isPending}
          aria-label={`Remover ${item.ticker} da lista`}
        >
          <Icon name="trash" size={18} />
        </button>
      </div>
    </li>
  );
}

export function WatchlistPage() {
  const { data, isLoading } = useWatchlist();
  const radar = useWatchlistRadar();
  const add = useAddWatchlist();
  const [ticker, setTicker] = useState("");

  const items = data?.items ?? [];
  const radarByTicker = new Map((radar.data?.items ?? []).map((r) => [r.ticker, r]));
  // radar responde 'é hora de comprar?': ordena pela margem sobre o teto (zona de compra no topo)
  const sorted = [...items].sort((a, b) => {
    const ma = radarByTicker.get(a.ticker.toUpperCase())?.margin;
    const mb = radarByTicker.get(b.ticker.toUpperCase())?.margin;
    if (ma == null && mb == null) return 0;
    if (ma == null) return 1;
    if (mb == null) return -1;
    return mb - ma;
  });
  const belowNow = (radar.data?.items ?? []).filter((r) => r.below_ceiling && !r.in_portfolio);

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
        Radar de zona de compra: preço, DY e situação vs preço-teto de Bazin
        {radar.data ? ` (DY-alvo ${pct(radar.data.bazin_target_yield)})` : ""} de cada ativo
        que você acompanha.
      </p>

      <p className="muted" style={{ marginTop: 0 }}>
        Acompanhamento. O aporte segue a <Link to="/alvo">carteira alvo</Link>.
      </p>

      {belowNow.length > 0 && (
        <div className="banner radar-banner">
          <strong>Abaixo do teto agora:</strong>{" "}
          {belowNow.slice(0, 6).map((r, i) => (
            <span key={r.ticker}>
              {i > 0 ? " · " : ""}
              <AssetLink ticker={r.ticker} />
              {r.margin != null ? ` (+${Math.round(r.margin * 100)}%)` : ""}
            </span>
          ))}
        </div>
      )}
      {radar.isLoading && <p className="muted">Calculando</p>}

      <form className="watchlist-add" onSubmit={submit}>
        <input
          placeholder="Ticker (ex.: PETR4)"
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          aria-label="Ticker para adicionar"
        />
        <button className="primary" type="submit" disabled={add.isPending || !ticker.trim() || duplicate}>
          {add.isPending ? "Adicionando" : "Adicionar"}
        </button>
      </form>
      {duplicate && <p className="field-error">{ticker.trim().toUpperCase()} já está na sua lista.</p>}
      {add.isError && (
        <div className="banner banner-error">
          <Icon name="alert" size={15} /> {add.error instanceof ApiError ? add.error.userMessage : "Não foi possível adicionar."}
        </div>
      )}

      {isLoading && <p className="muted">Carregando</p>}

      {!isLoading && items.length === 0 && (
        <div className="banner banner-warn">
          Lista vazia.
        </div>
      )}

      {items.length > 0 && (
        <ul className="cards">
          {sorted.map((i) => (
            <WatchlistRow key={i.ticker} item={i} radar={radarByTicker.get(i.ticker.toUpperCase())} />
          ))}
        </ul>
      )}

    </main>
  );
}
