import { useMemo, useState } from "react";
import { ApiError } from "../api/client";
import {
  useExposure,
  useFixedIncome,
  useIncome,
  usePerformance,
  usePortfolio,
  usePreferences,
} from "../api/queries";
import type { Position } from "../types";
import { PieChart, type Slice } from "../components/PieChart";
import { AssetLink } from "../components/AssetLink";
import { Tooltip } from "../components/Tooltip";
import { YocCell } from "../components/YocCell";
import { money, pct, signedPp } from "../lib/format";
import { PALETTE } from "../lib/palette";
import { PortfolioVsTarget } from "../components/PortfolioVsTarget";
import { PerformanceChart } from "../components/PerformanceChart";
import { buildComparison } from "../lib/comparison";
import { Icon } from "../components/Icon";

type GroupBy = "target" | "rendimento" | "asset" | "class" | "geography" | "sector";

const GROUPS: { key: GroupBy; label: string }[] = [
  { key: "target", label: "Atual × alvo" },
  { key: "rendimento", label: "Rendimento" },
  { key: "asset", label: "Por ativo" },
  { key: "class", label: "Por classe" },
  { key: "geography", label: "Por geografia" },
  { key: "sector", label: "Por setor" },
];

/** Dimensões cuja composição vem do backend: elas incluem a renda fixa marcada, e a
 *  aritmética (rateio de exposição parcial, metas, desvios) é testada lá. */
const FROM_EXPOSURE: GroupBy[] = ["class", "geography", "sector"];

// Desvio em p.p. com sinal (`signedPp`, importado de lib/format): a meta secundária é
// informativa, então o número aparece do lado do valor em vez de virar barra ou alerta.

interface Member {
  ticker: string;
  name: string | null;
  value: number; // contribuição da posição para este grupo
}
interface Group {
  label: string;
  value: number;
  members: Member[];
  targetPct?: number | null;
  deviationPp?: number | null;
}

/** Agrega as POSIÇÕES (renda variável) — usado só na visão "por ativo". */
function aggregate(positions: Position[]): Group[] {
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
    add(p.ticker, { ticker: p.ticker, name: p.name ?? null, value: p.value });
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
  const exposure = useExposure();
  const [perfWindow, setPerfWindow] = useState<string>("all");
  const performance = usePerformance(perfWindow);
  const income = useIncome();
  const fixedIncome = useFixedIncome(); // só pelo CDI de referência (SGS/BCB)
  const preferences = usePreferences();
  // abre na comparação: "como estou em relação ao que planejei" é a pergunta da aba
  const [by, setBy] = useState<GroupBy>("target");
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
  const groups = useMemo(() => {
    if (by === "asset") return aggregate(positions);
    if (!FROM_EXPOSURE.includes(by)) return [];
    const dim = (exposure.data?.dimensions ?? []).find((d) => d.dimension === by);
    return (dim?.items ?? []).map((i) => ({
      label: i.name,
      value: i.value,
      targetPct: i.target_pct,
      deviationPp: i.deviation_pp,
      members: (i.members ?? []).map((m) => ({
        ticker: m.label,
        name: m.name ?? null,
        value: m.value,
      })),
    }));
  }, [positions, by, exposure.data]);

  // Um total só para a página inteira: o patrimônio com a renda fixa que conta na carteira.
  // Enquanto a renda fixa vivia só na aba Reserva os dois números coincidiam; hoje, mostrar
  // o do Ghostfolio como "patrimônio" esconderia justamente o que o usuário acabou de marcar.
  const total = exposure.data?.total ?? pf?.total_value ?? 0;

  // A renda fixa das CONTAS vem do resumo da aba Reserva; a das posições atribuídas ao
  // bucket já está em `positions` e é somada dentro de `buildComparison`.
  const rendaFixaContas = fixedIncome.data?.portfolio_balance ?? 0;

  const comparison = useMemo(
    () =>
      buildComparison(
        positions,
        pf?.total_value ?? 0,
        preferences.data?.targets ?? {},
        preferences.data?.class_targets ?? {},
        {
          rendaFixaValue: rendaFixaContas,
          legacyInTotal: preferences.data?.legacy_in_total ?? true,
        },
      ),
    [positions, pf?.total_value, preferences.data, rendaFixaContas],
  );

  const slices: Slice[] = useMemo(
    () =>
      groups.map((g, i) => ({
        label: g.label,
        value: g.value,
        color: PALETTE[i % PALETTE.length],
      })),
    [groups],
  );

  // O denominador da rosca é a soma do que ela DESENHA, e a legenda usa o mesmo.
  // Antes a legenda dividia por `total` (patrimônio, com renda fixa) enquanto a rosca
  // dividia pela soma das fatias (só renda variável em "Por ativo"): dois totais a 100px
  // um do outro, e porcentagens que não fechavam 100%.
  const slicesTotal = useMemo(() => slices.reduce((s, x) => s + x.value, 0), [slices]);

  if (isLoading) return <main className="page"><p className="muted">Carregando</p></main>;

  if (error)
    return (
      <main className="page">
        <div className="banner banner-error">
          <Icon name="alert" size={15} /> Carteira indisponível:{" "}
          {error instanceof ApiError ? error.userMessage : "erro desconhecido"}
        </div>
      </main>
    );

  if (!pf) return <main className="page"><p className="muted">Carregando carteira…</p></main>;

  if (positions.length === 0)
    return (
      <main className="page">
        <div className="banner banner-warn">
          Nenhuma posição no Ghostfolio.
        </div>
      </main>
    );

  const selected = active != null ? groups[active] : null;
  const portfolioYoc = income.data?.yield_on_cost ?? null;
  const portfolioDy = income.data?.portfolio_yield ?? null;

  const ariaLabel = `Distribuição da carteira por ${
    GROUPS.find((g) => g.key === by)?.label ?? by
  }: ${slices.map((s) => `${s.label} ${pct(s.value / slicesTotal)}`).join(", ")}`;

  return (
    <main className="page">
      <div className="pf-summary">
        <span className="muted">Patrimônio total</span>
        <strong className="pf-total">{money(total)}</strong>
        <span className="muted">
          {positions.length} posições
          {(exposure.data?.rf_total ?? 0) > 0 && (
            <> · renda variável {money(exposure.data!.rv_total)} · renda fixa{" "}
              {money(exposure.data!.rf_total)}</>
          )}
        </span>
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

      {by === "target" && <PortfolioVsTarget comparison={comparison} />}

      {by === "rendimento" &&
        (performance.isLoading ? (
          <p className="muted">Carregando</p>
        ) : performance.data ? (
          <PerformanceChart
            data={performance.data}
            window={perfWindow}
            onWindow={setPerfWindow}
          />
        ) : (
          <p className="muted">Curva de rendimento indisponível.</p>
        ))}

      {by !== "target" && by !== "rendimento" && (
      <div className="pf-chart">
        <div className="pf-chart-pie">
          <PieChart slices={slices} active={active} onActive={setActive} ariaLabel={ariaLabel} />
        </div>
        <ul className="legend" role="list">
          {slices.map((s, i) => (
            <li
              key={s.label}
              role="listitem"
              tabIndex={0}
              aria-label={`${s.label}: ${money(s.value)}, ${pct(s.value / slicesTotal)}`}
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
                {money(s.value)} <span className="muted">· {pct(s.value / slicesTotal)}</span>
                {groups[i]?.deviationPp != null && (
                  <span className="muted legend-target">
                    {" "}
                    · meta {pct(groups[i].targetPct ?? 0)} ({signedPp(groups[i].deviationPp!)})
                  </span>
                )}
              </span>
            </li>
          ))}
        </ul>
      </div>
      )}

      {by === "geography" && (
        <p className="muted pf-note">
          Por domicílio do ativo, não por origem da receita.
        </p>
      )}
      {FROM_EXPOSURE.includes(by) && (exposure.data?.rf_total ?? 0) > 0 && (
        <p className="muted pf-note">
          Inclui {money(exposure.data!.rf_total)} de renda fixa marcada como parte da carteira.
        </p>
      )}

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
                      {money(p.value)} <span className="muted">· {pct(p.value / total)}</span>
                    </span>
                    <YocCell dividendYield={y?.dy} yieldOnCost={y?.yoc} />
                    {p.net_performance_pct != null && (
                      <Tooltip metricKey="net_performance">
                        <span
                          className={`pf-perf ${p.net_performance_pct >= 0 ? "pf-perf-up" : "pf-perf-down"}`}
                        >
                          {p.net_performance_pct >= 0 ? "+" : "−"}{pct(Math.abs(p.net_performance_pct))}
                        </span>
                      </Tooltip>
                    )}
                  </li>
                );
              })}
          </ul>
          <p className="muted" style={{ fontSize: 12 }}>
            Retorno = valorização + proventos desde a compra (Ghostfolio).
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
                  {money(m.value)} <span className="muted">· {pct(m.value / total)}</span>
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
