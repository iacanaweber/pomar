import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { Portfolio, Position } from "../types";
import { PieChart, type Slice } from "../components/PieChart";

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

const brl = (v: number) =>
  v.toLocaleString("pt-br", { style: "currency", currency: "BRL" });

/** Agrega as posições conforme a visão escolhida. Posições com várias tags/sem
 *  valor são tratadas para o total da pizza bater com o total da carteira. */
function aggregate(positions: Position[], by: GroupBy): { label: string; value: number }[] {
  const map = new Map<string, number>();
  const add = (k: string, v: number) => map.set(k, (map.get(k) ?? 0) + v);

  for (const p of positions) {
    if (by === "asset") add(p.ticker, p.value);
    else if (by === "class") add(p.asset_class || "OUTROS", p.value);
    else if (by === "sector") add(p.sector || "Sem setor", p.value);
    else {
      // por tag: divide o valor igualmente entre as tags da posição
      const tags = p.tags ?? [];
      if (tags.length === 0) add("Sem tag", p.value);
      else tags.forEach((t) => add(t, p.value / tags.length));
    }
  }

  let items = Array.from(map, ([label, value]) => ({ label, value })).sort(
    (a, b) => b.value - a.value,
  );

  // muitos itens: agrupa os menores em "Outros" para legibilidade
  if (items.length > 12) {
    const head = items.slice(0, 11);
    const tail = items.slice(11);
    head.push({ label: `Outros (${tail.length})`, value: tail.reduce((s, x) => s + x.value, 0) });
    items = head;
  }
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

  const slices: Slice[] = useMemo(() => {
    if (!pf) return [];
    return aggregate(pf.positions ?? [], by).map((d, i) => ({
      ...d,
      color: PALETTE[i % PALETTE.length],
    }));
  }, [pf, by]);

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

  return (
    <main className="page">
      <div className="pf-summary">
        <span className="muted">Patrimônio total</span>
        <strong className="pf-total">{brl(pf.total_value)}</strong>
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
          {slices.map((s, i) => {
            const pct = (s.value / pf.total_value) * 100;
            return (
              <li
                key={s.label}
                className={`legend-item ${active != null && active !== i ? "dim" : ""}`}
                onMouseEnter={() => setActive(i)}
                onMouseLeave={() => setActive(null)}
                onClick={() => setActive(active === i ? null : i)}
              >
                <span className="legend-dot" style={{ background: s.color }} />
                <span className="legend-label">{s.label}</span>
                <span className="legend-val">
                  {brl(s.value)} <span className="muted">· {pct.toFixed(1)}%</span>
                </span>
              </li>
            );
          })}
        </ul>
      </div>
    </main>
  );
}
