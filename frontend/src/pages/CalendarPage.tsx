import { useState } from "react";
import { useIncomeAnnounced, useIncomeCalendar } from "../api/queries";
import { AssetLink } from "../components/AssetLink";
import type { CalendarByAsset } from "../types";
import { isoToBR, money } from "../lib/format";

/** Proventos JÁ ANUNCIADOS (data e valor conhecidos) — agenda real, acima da sazonalidade. */
function AnnouncedSection() {
  const { data } = useIncomeAnnounced();
  const items = data?.items ?? [];
  if (items.length === 0) return null;
  return (
    <div className="alloc announced">
      <h3>
        Proventos anunciados{" "}
        {data && data.total_net > 0 && (
          <span className="cal-total">
            a receber <strong>{money(data.total_net, data.currency)}</strong>
          </span>
        )}
      </h3>
      <ul className="pf-drill-list">
        {items.map((a, i) => (
          <li key={`${a.ticker}-${i}`} className="pf-drill-item">
            <span className="pf-drill-ticker"><AssetLink ticker={a.ticker} /></span>
            <span className="muted">
              {a.payment_date ? `paga ${isoToBR(a.payment_date)}` : "pagamento a definir"}
              {a.type ? ` · ${a.type}` : ""} · {money(a.net_value_per_share)}/cota líq.
            </span>
            <span className="pf-drill-val">
              {a.total_net != null ? money(a.total_net, data?.currency) : "—"}
            </span>
          </li>
        ))}
      </ul>
      <p className="muted" style={{ fontSize: 12 }}>
        Anunciados pelas empresas (StatusInvest) para posições da sua carteira, líquidos de IR
        do JCP. Um anúncio que some pode indicar corte.
      </p>
    </div>
  );
}

const MONTH_NAMES = [
  "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
  "Jul", "Ago", "Set", "Out", "Nov", "Dez",
];

const currentMonth = new Date().getMonth() + 1; // 1..12

function asByAsset(raw: { [key: string]: unknown }[] | undefined): CalendarByAsset[] {
  return (raw ?? [])
    .map((r) => ({ ticker: String(r.ticker ?? ""), income: Number(r.income ?? 0) }))
    .filter((r) => r.ticker);
}

export function CalendarPage() {
  const { data, isLoading, error } = useIncomeCalendar();
  const [open, setOpen] = useState<number | null>(null);

  if (isLoading)
    return (
      <main className="page">
        <h2>Calendário de proventos</h2>
        <ul className="cards">
          {Array.from({ length: 6 }).map((_, i) => (
            <li key={i} className="card cal-skeleton" aria-hidden="true" />
          ))}
        </ul>
      </main>
    );

  if (error)
    return (
      <main className="page">
        <h2>Calendário de proventos</h2>
        <div className="banner banner-error">⚠️ Não consegui montar o calendário agora.</div>
      </main>
    );

  const months = data?.months ?? [];
  const maxIncome = Math.max(1, ...months.map((m) => m.income));
  const hasData = months.some((m) => m.income > 0);

  return (
    <main className="page">
      <div className="cal-header">
        <h2 style={{ margin: 0 }}>Calendário de proventos</h2>
        {data && (
          <span className="cal-total">
            Total no ano <strong>{money(data.annual_total, data.currency)}</strong>
          </span>
        )}
      </div>
      {data && <p className="muted" style={{ marginTop: 0 }}>{data.basis}</p>}

      <AnnouncedSection />

      {(data?.warnings ?? []).length > 0 && (
        <div className="banner banner-warn">
          {(data?.warnings ?? []).map((w, i) => (
            <div key={i}>• {w}</div>
          ))}
        </div>
      )}

      {!hasData ? (
        <div className="banner banner-warn">
          Conecte sua carteira para ver a renda projetada mês a mês.
        </div>
      ) : (
        <ul className="cal-list">
          {months.map((m) => {
            const byAsset = asByAsset(m.by_asset);
            const isOpen = open === m.month;
            const isCurrent = m.month === currentMonth;
            const widthPct = Math.round((m.income / maxIncome) * 100);
            const hasDrill = byAsset.length > 0;
            return (
              <li key={m.month} className={`cal-month ${isCurrent ? "cal-current" : ""}`}>
                <button
                  className="cal-month-head"
                  onClick={() => hasDrill && setOpen(isOpen ? null : m.month)}
                  aria-expanded={hasDrill ? isOpen : undefined}
                  aria-label={`${MONTH_NAMES[m.month - 1]}: ${money(m.income, data?.currency)}`}
                >
                  <span className="cal-month-name">
                    {MONTH_NAMES[m.month - 1]}
                    {isCurrent && <span className="cal-now-tag"> · este mês</span>}
                  </span>
                  <span className="cal-bar-track">
                    <span className="cal-bar-fill" style={{ width: `${widthPct}%` }} />
                  </span>
                  <span className="cal-month-val">{money(m.income, data?.currency)}</span>
                  {hasDrill && <span className="card-toggle">{isOpen ? "▾" : "▸"}</span>}
                </button>
                {isOpen && hasDrill && (
                  <ul className="cal-byasset">
                    {byAsset.map((a) => (
                      <li key={a.ticker}>
                        <AssetLink ticker={a.ticker} />
                        <span className="muted"> {money(a.income, data?.currency)}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            );
          })}
        </ul>
      )}

      <p className="disclaimer">
        Estimativa sazonal a partir do histórico — os proventos reais variam mês a mês.
      </p>
    </main>
  );
}
