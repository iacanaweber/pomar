import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { Portfolio, Position } from "../types";
import { PieChart, type Slice } from "../components/PieChart";
import { AssetLink } from "../components/AssetLink";
import { money, pct } from "../lib/format";

type GroupBy = "asset" | "class" | "sector" | "tag";

const GROUPS: { key: GroupBy; label: string }[] = [
  { key: "asset", label: "Por ativo" },
  { key: "class", label: "Por classe" },
  { key: "sector", label: "Por setor" },
  { key: "tag", label: "Por tag" },
];

// Paleta com tons de verde/terra + acentos, suficiente para muitas fatias.
const PALETTE = [
  "#2e7d32", "#66bb6a", "#f9a825", "#1b5e20", "#9ccc65", "#ef6c00",
  "#26a69a", "#8d6e63", "#5c6bc0", "#ec407a", "#789262", "#ffb300",
  "#00897b", "#c0ca33", "#6d4c41", "#42a5f5",
];

interface Member {
  ticker: string;
  name: string | null;
  value: number; // contribuição da posição para este grupo (no caso de tag, valor rateado)
}
interface Group {
  label: string;
  value: number;
  members: Member[];
}

/** Agrega as posições conforme a visão escolhida, guardando os ATIVOS de cada grupo
 *  (para o detalhamento ao clicar numa fatia). */
function aggregate(positions: Position[], by: GroupBy): Group[] {
  const map = new Map<string, Group>();
  const add = (key: string, m: Member) => {
    let g = map.get(key);
    if (!g) {
      g = { label: key, value: 0, members: [] };
      map.set(key, g);
    }
    g.value += m.value;
    g.members.push(m);
  };

  for (const p of positions) {
    const base = { ticker: p.ticker, name: p.name ?? null };
    if (by === "asset") add(p.ticker, { ...base, value: p.value });
    else if (by === "class") add(p.asset_class || "OUTROS", { ...base, value: p.value });
    else if (by === "sector") add(p.sector || "Sem setor", { ...base, value: p.value });
    else {
      const tags = p.tags ?? [];
      if (tags.length === 0) add("Sem tag", { ...base, value: p.value });
      else tags.forEach((t) => add(t, { ...base, value: p.value / tags.length }));
    }
  }

  let items = Array.from(map.values()).sort((a, b) => b.value - a.value);
  // muitos itens: agrupa os menores em "Outros" (mantendo seus ativos no detalhamento)
  if (items.length > 12) {
    const head = items.slice(0, 11);
    const tail = items.slice(11);
    head.push({
      label: `Outros (${tail.length})`,
      value: tail.reduce((s, x) => s + x.value, 0),
      members: tail.flatMap((g) => g.members),
    });
    items = head;
  }
  // ativos de cada grupo ordenados por valor
  items.forEach((g) => g.members.sort((a, b) => b.value - a.value));
  return items;
}

export function PortfolioPage() {
  const [pf, setPf] = useState<Portfolio | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [by, setBy] = useState<GroupBy>("class");
  const [active, setActive] = useState<number | null>(null);

  useEffect(() => {
    api.portfolio().then(setPf).catch((e) => setError(e.message));
  }, []);

  const groups = useMemo(() => (pf ? aggregate(pf.positions ?? [], by) : []), [pf, by]);
  const slices: Slice[] = useMemo(
    () => groups.map((g, i) => ({ label: g.label, value: g.value, color: PALETTE[i % PALETTE.length] })),
    [groups],
  );

  if (error)
    return (
      <main className="page">
        <div className="banner banner-error">
          ⚠️ Não consegui ler sua carteira no Ghostfolio: {error}
        </div>
      </main>
    );

  if (!pf) return <main className="page"><p className="muted">Carregando carteira…</p></main>;

  if ((pf.positions ?? []).length === 0)
    return (
      <main className="page">
        <div className="banner banner-warn">
          Nenhuma posição encontrada no Ghostfolio. Confira a conexão e seus lançamentos.
        </div>
      </main>
    );

  const selected = active != null ? groups[active] : null;

  return (
    <main className="page">
      <div className="pf-summary">
        <span className="muted">Patrimônio total</span>
        <strong className="pf-total">{money(pf.total_value)}</strong>
        <span className="muted">{(pf.positions ?? []).length} posições</span>
      </div>

      <div className="seg">
        {GROUPS.map((g) => (
          <button
            key={g.key}
            className={`seg-btn ${by === g.key ? "seg-on" : ""}`}
            onClick={() => {
              setBy(g.key);
              setActive(null);
            }}
          >
            {g.label}
          </button>
        ))}
      </div>

      <div className="pf-chart">
        <PieChart slices={slices} active={active} onActive={setActive} />
        <ul className="legend">
          {slices.map((s, i) => (
            <li
              key={s.label}
              className={`legend-item ${active != null && active !== i ? "dim" : ""} ${active === i ? "legend-on" : ""}`}
              onClick={() => setActive(active === i ? null : i)}
            >
              <span className="legend-dot" style={{ background: s.color }} />
              <span className="legend-label">{s.label}</span>
              <span className="legend-val">
                {money(s.value)} <span className="muted">· {pct(s.value / pf.total_value)}</span>
              </span>
            </li>
          ))}
        </ul>
      </div>

      {selected && by !== "asset" && (
        <div className="pf-drill">
          <h3>
            Ativos em <span className="pf-drill-group">{selected.label}</span>{" "}
            <span className="muted">
              · {selected.members.length}{" "}
              {selected.members.length === 1 ? "ativo" : "ativos"} · {money(selected.value)}
            </span>
          </h3>
          <ul className="pf-drill-list">
            {selected.members.map((m) => (
              <li key={m.ticker} className="pf-drill-item">
                <span className="pf-drill-ticker"><AssetLink ticker={m.ticker} /></span>
                {m.name && <span className="pf-drill-name">{m.name}</span>}
                <span className="pf-drill-val">
                  {money(m.value)} <span className="muted">· {pct(m.value / pf.total_value)}</span>
                </span>
              </li>
            ))}
          </ul>
          <button className="link-button" onClick={() => setActive(null)}>
            Fechar detalhamento
          </button>
        </div>
      )}
    </main>
  );
}
