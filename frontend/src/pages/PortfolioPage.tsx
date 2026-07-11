import { useMemo, useState } from "react";
import { ApiError } from "../api/client";
import { useFixedIncome, useIncome, usePortfolio } from "../api/queries";
import type { Position } from "../types";
import { PieChart, type Slice } from "../components/PieChart";
import { AssetLink } from "../components/AssetLink";
import { Tooltip } from "../components/Tooltip";
import { YocCell } from "../components/YocCell";
import { money, pct } from "../lib/format";
import { BESST_COLORS, BESST_DEFENSIVE, PALETTE, besstCategory } from "../lib/palette";

type GroupBy = "asset" | "class" | "sector" | "tag" | "besst";

const GROUPS: { key: GroupBy; label: string }[] = [
  { key: "asset", label: "Por ativo" },
  { key: "class", label: "Por classe" },
  { key: "sector", label: "Por setor" },
  { key: "tag", label: "Por tag" },
  { key: "besst", label: "BESST" },
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
    else if (by === "besst") add(besstCategory(p.sector), { ...base, value: p.value });
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
  const { data: pf, isLoading, error } = usePortfolio();
  const income = useIncome();
  const fixedIncome = useFixedIncome(); // só pelo CDI de referência (SGS/BCB)
  const [by, setBy] = useState<GroupBy>("class");
  const [active, setActive] = useState<number | null>(null);

  // DY/YoC por ticker, a partir da renda passiva (única fonte com DY de mercado por ativo).
  const yieldByTicker = useMemo(() => {
    const m = new Map<string, { dy?: number | null; yoc?: number | null }>();
    for (const a of income.data?.by_asset ?? []) {
      m.set(a.ticker, { dy: a.dividend_yield, yoc: a.yield_on_cost });
    }
    return m;
  }, [income.data]);

  const positions = pf?.positions ?? [];
  const groups = useMemo(() => aggregate(positions, by), [positions, by]);

  const slices: Slice[] = useMemo(
    () =>
      groups.map((g, i) => ({
        label: g.label,
        value: g.value,
        color: by === "besst" ? BESST_COLORS[besstCategory(g.label)] : PALETTE[i % PALETTE.length],
      })),
    [groups, by],
  );

  // % defensivo (BESST): soma das categorias essenciais ÷ total.
  const defensivePct = useMemo(() => {
    if (by !== "besst") return null;
    const total = groups.reduce((s, g) => s + g.value, 0) || 1;
    const def = groups
      .filter((g) => (BESST_DEFENSIVE as string[]).includes(g.label))
      .reduce((s, g) => s + g.value, 0);
    return def / total;
  }, [groups, by]);

  if (isLoading) return <main className="page"><p className="muted">Carregando carteira…</p></main>;

  if (error)
    return (
      <main className="page">
        <div className="banner banner-error">
          ⚠️ Não consegui ler sua carteira no Ghostfolio:{" "}
          {error instanceof ApiError ? error.userMessage : "erro desconhecido"}
        </div>
      </main>
    );

  if (!pf) return <main className="page"><p className="muted">Carregando carteira…</p></main>;

  if (positions.length === 0)
    return (
      <main className="page">
        <div className="banner banner-warn">
          Nenhuma posição encontrada no Ghostfolio. Confira a conexão e seus lançamentos.
        </div>
      </main>
    );

  const selected = active != null ? groups[active] : null;
  const portfolioYoc = income.data?.yield_on_cost ?? null;
  const portfolioDy = income.data?.portfolio_yield ?? null;

  const ariaLabel = `Distribuição da carteira por ${
    GROUPS.find((g) => g.key === by)?.label ?? by
  }: ${slices.map((s) => `${s.label} ${pct(s.value / pf.total_value)}`).join(", ")}`;

  return (
    <main className="page">
      <div className="pf-summary">
        <span className="muted">Patrimônio total</span>
        <strong className="pf-total">{money(pf.total_value)}</strong>
        <span className="muted">{positions.length} posições</span>
        {(portfolioDy != null || portfolioYoc != null) && (
          <span className="pf-yields">
            {portfolioYoc != null && (
              <Tooltip metricKey="yield_on_cost">
                <span>YoC carteira <strong>{pct(portfolioYoc)}</strong></span>
              </Tooltip>
            )}
            {portfolioDy != null && (
              <Tooltip metricKey="div_yield">
                <span> · DY <strong>{pct(portfolioDy)}</strong></span>
              </Tooltip>
            )}
            {fixedIncome.data?.cdi_annual != null && (
              <span className="muted"> · CDI referência {pct(fixedIncome.data.cdi_annual)} a.a.</span>
            )}
          </span>
        )}
      </div>

      <div className="seg" role="tablist">
        {GROUPS.map((g) => (
          <button
            key={g.key}
            role="tab"
            aria-selected={by === g.key}
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
        <div className="pf-chart-pie">
          <PieChart slices={slices} active={active} onActive={setActive} ariaLabel={ariaLabel} />
          {by === "besst" && defensivePct != null && (
            <p className="besst-center-note">
              {pct(defensivePct, 0)} em setores perenes (defensivo)
            </p>
          )}
        </div>
        <ul className="legend" role="list">
          {slices.map((s, i) => (
            <li
              key={s.label}
              role="listitem"
              tabIndex={0}
              aria-label={`${s.label}: ${money(s.value)}, ${pct(s.value / pf.total_value)}`}
              className={`legend-item ${active != null && active !== i ? "dim" : ""} ${active === i ? "legend-on" : ""}`}
              onClick={() => setActive(active === i ? null : i)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setActive(active === i ? null : i);
                }
              }}
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

      {by === "asset" && (
        <div className="pf-drill">
          <h3>Por ativo · DY, Yield on Cost e retorno</h3>
          <ul className="pf-drill-list">
            {[...positions]
              .sort((a, b) => b.value - a.value)
              .map((p) => {
                const y = yieldByTicker.get(p.ticker);
                return (
                  <li key={p.ticker} className="pf-drill-item pf-asset-row">
                    <span className="pf-drill-ticker"><AssetLink ticker={p.ticker} /></span>
                    <span className="pf-asset-val">
                      {money(p.value)} <span className="muted">· {pct(p.value / pf.total_value)}</span>
                    </span>
                    <YocCell dividendYield={y?.dy} yieldOnCost={y?.yoc} />
                    {p.net_performance_pct != null && (
                      <Tooltip metricKey="net_performance">
                        <span
                          className={`pf-perf ${p.net_performance_pct >= 0 ? "pf-perf-up" : "pf-perf-down"}`}
                        >
                          {p.net_performance_pct >= 0 ? "▲" : "▼"} {pct(Math.abs(p.net_performance_pct))}
                        </span>
                      </Tooltip>
                    )}
                  </li>
                );
              })}
          </ul>
          <p className="muted" style={{ fontSize: 12 }}>
            Retorno = valorização + proventos desde a compra (Ghostfolio). Compare com o CDI do
            período antes de tirar conclusões — anos ruins fazem parte do método.
          </p>
        </div>
      )}

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
