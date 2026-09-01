import { useMemo, useState } from "react";
import type { PerformanceResponse } from "../types";
import { money, signedPct } from "../lib/format";
import { Icon } from "./Icon";
import { Tooltip } from "./Tooltip";

/** Quatro comparações por vez, no máximo.
 *
 *  Não é preferência estética: o validador de paleta (skill dataviz) mostra que nem
 *  quatro matizes sobrevivem a daltonismo quando as linhas podem se cruzar em qualquer
 *  ordem. Acima disso, cor deixa de identificar e o gráfico vira emaranhado. A ordem
 *  abaixo é FIXA por série — ligar ou desligar uma nunca repinta as outras. */
const MAX_SERIES = 4;

/** Slots validados (adjacentes, claro e escuro) na ordem magenta → azul → laranja →
 *  verde-azulado. A carteira NÃO ocupa slot: ela usa o verde do app, porque é a
 *  identidade da tela e não mais uma categoria. */
const SLOT_COLORS = ["var(--perf-1)", "var(--perf-2)", "var(--perf-3)", "var(--perf-4)"];

/** Traço é a codificação SECUNDÁRIA obrigatória: com a separação sob daltonismo no piso,
 *  a identidade não pode descansar só na cor. Cada série ganha padrão próprio, e o rótulo
 *  na ponta direita fecha a leitura sem depender de hover. */
const SLOT_DASH = ["0", "7 4", "2 3", "10 3 2 3"];

/** Séries ligadas por padrão: a carteira, a estratégia do próprio usuário (o único
 *  comparável defensável) e as duas referências que ele reconhece. */
const DEFAULT_ON = ["COMPOSITE", "IBOV", "CDI"];

const WINDOWS = [
  { key: "3m", label: "3 meses" },
  { key: "6m", label: "6 meses" },
  { key: "12m", label: "12 meses" },
  { key: "all", label: "Tudo" },
] as const;

const shortWeek = (weekEnd: string) => {
  const [, m, d] = weekEnd.split("-");
  return `${d}/${m}`;
};

interface Serie {
  code: string;
  label: string;
  values: (number | null)[];
  color: string;
  dash: string;
  hero?: boolean;
  proxy?: string | null;
}

/** Curva de rendimento: TWR acumulado da carteira contra os índices.
 *
 *  Um eixo só, sempre. As séries são todas retorno acumulado em fração desde o início da
 *  janela — é isso que as torna comparáveis, e é por isso que o valor em R$ da carteira
 *  (que cresce por aporte) NÃO entra aqui.
 */
export function PerformanceChart({
  data,
  window: window_,
  onWindow,
}: {
  data: PerformanceResponse;
  window: string;
  /** A janela é do SERVIDOR (ela recorta a série e reencadeia o TWR), então o estado
   *  mora na página e a troca refaz a busca — não é um filtro de exibição. */
  onWindow: (w: string) => void;
}) {
  const [on, setOn] = useState<string[]>(DEFAULT_ON);
  const [hover, setHover] = useState<number | null>(null);
  const [tabela, setTabela] = useState(false);

  // Idem: sem memo, os `?? []` refazem o useMemo das séries a cada render.
  const points = useMemo(() => data.points ?? [], [data.points]);
  const disponiveis = useMemo(() => data.benchmarks ?? [], [data.benchmarks]);

  const series: Serie[] = useMemo(() => {
    const carteira: Serie = {
      code: "PORTFOLIO",
      label: "Sua carteira",
      values: points.map((p) => p.twr_cumulative ?? null),
      color: "var(--perf-hero)",
      dash: "0",
      hero: true,
    };
    const escolhidas = disponiveis
      .filter((b) => on.includes(b.code))
      .slice(0, MAX_SERIES)
      .map((b, i) => ({
        code: b.code,
        label: b.label,
        values: b.values ?? [],
        color: SLOT_COLORS[i],
        dash: SLOT_DASH[i],
        proxy: b.proxy,
      }));
    return [carteira, ...escolhidas];
  }, [points, disponiveis, on]);

  const toggle = (code: string) =>
    setOn((s) =>
      s.includes(code) ? s.filter((c) => c !== code) : s.length >= MAX_SERIES ? s : [...s, code],
    );

  if (points.length === 0) {
    return (
      <section className="card perf-empty">
        <h3>Curva de rendimento</h3>
        {(data.warnings ?? []).map((w, i) => (
          <p className="muted" key={i}>
            {w}
          </p>
        ))}
      </section>
    );
  }

  // Com menos de quatro pontos, uma linha sugere uma tendência que ainda não existe.
  const poucosPontos = points.length < 4;

  const todos = series.flatMap((s) => s.values.filter((v): v is number => v != null));
  const min = Math.min(0, ...todos);
  const max = Math.max(0, ...todos);
  const span = max - min || 0.02;
  const pad = span * 0.12;
  const y0 = min - pad;
  const y1 = max + pad;

  const W = 640;
  const H = 260;
  const ML = 8;
  const MR = 64; // espaço do rótulo direto na ponta
  const MT = 12;
  const MB = 26;

  const x = (i: number) =>
    ML + (points.length <= 1 ? 0 : (i / (points.length - 1)) * (W - ML - MR));
  const y = (v: number) => MT + (1 - (v - y0) / (y1 - y0)) * (H - MT - MB);

  const path = (values: (number | null)[]) => {
    let d = "";
    let aberto = false;
    values.forEach((v, i) => {
      if (v == null) {
        aberto = false; // lacuna: o traço PARA, não interpola
        return;
      }
      d += `${aberto ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)} `;
      aberto = true;
    });
    return d.trim();
  };

  const zeroY = y(0);
  const ativo = hover ?? points.length - 1;

  return (
    <section className="card perf">
      <div className="perf-head">
        <h3>Curva de rendimento</h3>
        <div className="seg perf-window" aria-label="Janela">
          {WINDOWS.map((w) => (
            <button
              key={w.key}
              aria-pressed={window_ === w.key}
              className={`seg-btn ${window_ === w.key ? "seg-on" : ""}`}
              onClick={() => onWindow(w.key)}
            >
              {w.label}
            </button>
          ))}
        </div>
      </div>

      {/* Os dois números respondem perguntas diferentes e por isso ficam lado a lado, com
          rótulo curto e distinto — não são duas versões do mesmo. */}
      <div className="perf-stats">
        <div className="perf-stat">
          <Tooltip metricKey="twr">
            <span className="muted">TWR</span>
          </Tooltip>
          <strong className={(data.twr ?? 0) >= 0 ? "perf-up" : "perf-down"}>
            {signedPct(data.twr)}
          </strong>
          {data.twr_annualized != null && (
            <span className="muted">{signedPct(data.twr_annualized)} a.a.</span>
          )}
        </div>
        <div className="perf-stat">
          <span className="muted">XIRR · quanto o seu dinheiro rendeu</span>
          <strong className={(data.xirr ?? 0) >= 0 ? "perf-up" : "perf-down"}>
            {data.xirr == null ? "—" : `${signedPct(data.xirr)} a.a.`}
          </strong>
          <span className="muted">não se compara a índice</span>
        </div>
        <div className="perf-stat">
          <span className="muted">Patrimônio</span>
          <strong>{money(data.current_value)}</strong>
        </div>
      </div>

      {poucosPontos ? (
        <PerformanceTable data={data} series={series} />
      ) : (
        <>
          <div className="perf-plot">
            <svg
              viewBox={`0 0 ${W} ${H}`}
              className="perf-svg"
              role="img"
              aria-label={`Retorno acumulado: sua carteira ${signedPct(data.twr)} em ${points.length} semanas`}
              onMouseLeave={() => setHover(null)}
            >
              {/* zero é a única linha de grade que carrega significado: acima dela é ganho */}
              <line x1={ML} x2={W - MR} y1={zeroY} y2={zeroY} className="perf-zero" />
              {series.map((s) => (
                <path
                  key={s.code}
                  d={path(s.values)}
                  fill="none"
                  stroke={s.color}
                  strokeWidth={s.hero ? 3 : 2}
                  strokeDasharray={s.dash === "0" ? undefined : s.dash}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              ))}
              {/* rótulo direto na ponta: identidade sem depender de cor nem de hover */}
              {series.map((s) => {
                const ultimo = [...s.values].reverse().find((v) => v != null);
                if (ultimo == null) return null;
                return (
                  <text
                    key={s.code}
                    x={W - MR + 6}
                    y={y(ultimo) + 4}
                    className={`perf-label ${s.hero ? "perf-label-hero" : ""}`}
                  >
                    {signedPct(ultimo)}
                  </text>
                );
              })}
              {/* alvo de toque por ponto, bem maior que a marca */}
              {points.map((p, i) => (
                <rect
                  key={p.week_of}
                  x={x(i) - 12}
                  y={0}
                  width={24}
                  height={H}
                  fill="transparent"
                  onMouseEnter={() => setHover(i)}
                  aria-hidden="true"
                />
              ))}
              {hover != null && (
                <line x1={x(hover)} x2={x(hover)} y1={MT} y2={H - MB} className="perf-crosshair" />
              )}
              {points.map((p, i) =>
                p.late ? (
                  // captura fora da janela do domingo: marcada, para o gráfico não mentir
                  // sobre a data do dado
                  <circle key={p.week_of} cx={x(i)} cy={H - MB + 8} r={2.5} className="perf-late" />
                ) : null,
              )}
              <text x={ML} y={H - 6} className="perf-axis">
                {shortWeek(points[0].week_end)}
              </text>
              <text x={W - MR} y={H - 6} textAnchor="end" className="perf-axis">
                {shortWeek(points[points.length - 1].week_end)}
              </text>
            </svg>
          </div>

          <p className="perf-readout">
            Semana de <strong>{shortWeek(points[ativo].week_end)}</strong>:{" "}
            {series.map((s) => (
              <span key={s.code} className="perf-readout-item">
                <span className="perf-swatch" style={{ background: s.color }} aria-hidden="true" />
                {s.label} {signedPct(s.values[ativo])}
              </span>
            ))}
          </p>
        </>
      )}

      <ul className="perf-legend">
        <li className="perf-legend-item perf-legend-hero">
          <span
            className="perf-swatch"
            style={{ background: "var(--perf-hero)" }}
            aria-hidden="true"
          />
          <span>Sua carteira (TWR)</span>
        </li>
        {disponiveis.map((b) => {
          const ligada = on.includes(b.code);
          const slot = series.findIndex((s) => s.code === b.code);
          const cheio = !ligada && on.length >= MAX_SERIES;
          return (
            <li key={b.code}>
              <button
                type="button"
                className={`perf-legend-item ${ligada ? "perf-on" : ""}`}
                aria-pressed={ligada}
                disabled={cheio}
                title={cheio ? `Máximo de ${MAX_SERIES} comparações` : b.source}
                onClick={() => toggle(b.code)}
              >
                <span
                  className="perf-swatch"
                  style={{ background: ligada && slot > 0 ? series[slot].color : "var(--muted)" }}
                  aria-hidden="true"
                />
                <span>{b.label}</span>
                {b.proxy && <span className="muted perf-proxy">via {b.proxy}</span>}
              </button>
            </li>
          );
        })}
      </ul>

      {/* Os retângulos de hover do SVG deixaram de ser paradas de tabulação: eram uma
          POR SEMANA de histórico, anunciadas como botão, e nenhuma fazia nada ao ser
          acionada. Os números seguem alcançáveis pelo teclado — aqui, na tabela que já
          existia para o caso de poucos pontos. */}
      {!poucosPontos && (
        <>
          <button
            type="button"
            className="link-button"
            aria-expanded={tabela}
            onClick={() => setTabela((v) => !v)}
          >
            <Icon name="chevron" size={16} /> {tabela ? "Ocultar os números" : "Ver os números"}
          </button>
          {tabela && <PerformanceTable data={data} series={series} />}
        </>
      )}

      <p className="muted perf-note">
        Séries partem de zero no início da janela.
        {series.some((s) => s.proxy) && " “via”: proxy por ETF, com taxa e desvio."}
      </p>

      {(data.warnings ?? []).map((w, i) => (
        <p className="muted perf-note" key={i}>
          {w}
        </p>
      ))}
    </section>
  );
}

/** Com menos de quatro pontos a tabela é mais honesta que a linha: ela informa sem
 *  desenhar uma inclinação que ainda não significa nada. */
function PerformanceTable({ data, series }: { data: PerformanceResponse; series: Serie[] }) {
  const points = data.points ?? [];
  return (
    <div className="perf-table-wrap">
      <table className="perf-table">
        <thead>
          <tr>
            <th scope="col">Semana</th>
            <th scope="col">Patrimônio</th>
            <th scope="col">Aporte</th>
            {series.map((s) => (
              <th scope="col" key={s.code}>
                {s.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {points.map((p, i) => (
            <tr key={p.week_of}>
              <th scope="row">
                {p.week_end}
                {p.late && <span className="muted"> · atrasado</span>}
              </th>
              <td>{money(p.total_value)}</td>
              <td>{p.flow_net ? money(p.flow_net) : "—"}</td>
              {series.map((s) => (
                <td key={s.code}>{signedPct(s.values[i])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
