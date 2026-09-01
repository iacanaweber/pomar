import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import {
  useAssignments,
  useAsset,
  useLabels,
  useSetAssignments,
  useYocHistory,
} from "../api/queries";
import { CeilingBadge } from "../components/CeilingBadge";
import { MutationError } from "../components/MutationError";
import { Tooltip } from "../components/Tooltip";
import type { Fundamentals, LabelOut } from "../types";
import { money, pct } from "../lib/format";
import { classLabel, temMetricasDeAcao } from "../lib/classes";
import { Icon } from "../components/Icon";

/** Evolução do Yield on Cost, a partir dos snapshots mensais: quanto a posição rende
 *  sobre o PREÇO PAGO, e para onde esse número foi desde o primeiro snapshot. */
function YocEvolution({ ticker }: { ticker: string }) {
  const { data } = useYocHistory(ticker);
  const points = (data ?? []).filter((p) => p.yoc != null);
  if (points.length < 2) return null;
  const first = points[0];
  const last = points[points.length - 1];
  const trend = (last.yoc ?? 0) - (first.yoc ?? 0);
  return (
    <div className="alloc">
      <h3>
        <Tooltip metricKey="yield_on_cost">
          <span>Evolução do Yield on Cost</span>
        </Tooltip>
      </h3>
      <p style={{ marginTop: 0 }}>
        De <strong>{pct(first.yoc ?? 0)}</strong> em {first.month} para{" "}
        <strong>{pct(last.yoc ?? 0)}</strong> em {last.month}
        {trend > 0.001 ? " — em alta." : trend < -0.001 ? " — em queda." : ""}
      </p>
    </div>
  );
}

/** Rótulos do ativo que o usuário pode sobrescrever: a cesta em que ele é comprado
 *  (bucket, que DIRIGE a compra) e o domicílio (geografia, só visualização).
 *
 *  A geografia mostra de onde veio o rótulo: "(default)" quando é o mapa curado, sem
 *  sufixo quando foi escolha do usuário. Sem essa distinção, um default plausível pareceria
 *  uma decisão que ele nunca tomou. */
function AssetLabels({ ticker, assetClass }: { ticker: string; assetClass: string }) {
  const buckets = useLabels("bucket");
  const geos = useLabels("geography");
  const setAssignments = useSetAssignments();
  const atual = useAssignments({
    dimension: "geography",
    subjectType: "ticker",
    subjects: [ticker],
    includeDefaults: true,
  });
  const bucketAtual = useAssignments({
    dimension: "bucket",
    subjectType: "ticker",
    subjects: [ticker],
  });

  const geo = atual.data?.[0];
  const bucket = bucketAtual.data?.[0];

  // `labels` é obrigatório: a função atende duas dimensões, e um valor padrão apontando
  // para uma delas fazia a outra procurar o código na lista errada.
  const salvar = (dimension: "bucket" | "geography", code: string, labels: LabelOut[] | undefined) => {
    const label = (labels ?? []).find((l) => l.code === code);
    setAssignments.mutate({
      subject_type: "ticker",
      subject_id: ticker,
      dimension,
      items: label ? [{ label_id: label.id, weight: 1 }] : [],
    });
  };

  return (
    <div className="alloc asset-labels">
      <h3 style={{ marginTop: 0 }}>Classificação</h3>
      <div className="adv-row">
        <label className="field">
          <span>Cesta na carteira alvo</span>
          <select
            value={bucket?.code ?? ""}
            onChange={(e) => salvar("bucket", e.target.value, buckets.data)}
          >
            <option value="">Automática ({assetClass})</option>
            {(buckets.data ?? []).map((l) => (
              <option key={l.id} value={l.code}>
                {l.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Geografia</span>
          {/* Sem atribuição, valor vazio com opção própria — o `?? "BR"` de antes casava
              com nenhuma opção quando "BR" não estava na lista, e o navegador exibia em
              silêncio a primeira da lista como se fosse a escolhida. */}
          <select
            value={geo?.code ?? ""}
            onChange={(e) => salvar("geography", e.target.value, geos.data)}
          >
            <option value="">Automática (mapa do app)</option>
            {(geos.data ?? []).map((l) => (
              <option key={l.id} value={l.code}>
                {l.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      <p className="muted" style={{ fontSize: 12, margin: 0 }}>
        {geo && geo.source !== "user"
          ? `Geografia: ${geo.name} (mapa do app).`
          : "Geografia definida manualmente."}
      </p>
      <p className="muted" style={{ fontSize: 12, margin: 0 }}>
        Cesta manual tem precedência sobre a automática.
      </p>
      {/* Sem isto, mudar a cesta e falhar revertia no próximo refetch, sem explicação. */}
      <MutationError error={setAssignments.error} acao="salvar a classificação" />
    </div>
  );
}

const RISK_CLASS: Record<string, string> = {
  verde: "risk-verde",
  amarelo: "risk-amarelo",
  vermelho: "risk-vermelho",
};

/** O selo diz o que os dados mostram, não uma nota: sem alerta / atenção / risco alto. */
const RISK_LABEL: Record<string, string> = {
  verde: "sem alertas",
  amarelo: "atenção",
  vermelho: "risco alto",
};

function Fund({ label, value }: { label: string; value: string | null }) {
  if (value == null) return null;
  return (
    <div className="fund-item">
      <span className="muted">{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export function AssetPage() {
  const { ticker = "" } = useParams();
  const navigate = useNavigate();
  const { data, isLoading, error } = useAsset(ticker);

  if (isLoading)
    return (
      <main className="page">
        <p className="muted" role="status">Carregando {ticker}…</p>
      </main>
    );
  if (error || !data)
    return (
      <main className="page">
        <button className="link-button" onClick={() => navigate(-1)}>
          ← voltar
        </button>
        <div className="banner banner-error">
          {error instanceof ApiError ? error.userMessage : `Sem dados de ${ticker}.`}
        </div>
      </main>
    );

  const { asset, analysis } = data;
  const f = (asset.fundamentals ?? {}) as Fundamentals;
  // Preço-teto, YoC, fundamentos e proventos só dizem algo para ação e FII — o legado da
  // estratégia anterior. Num ETF de acumulação a grade vinha vazia e o teto, sem sentido.
  const legado = temMetricasDeAcao(asset.asset_class);
  const riskClass = RISK_CLASS[analysis.risk_level ?? "verde"] ?? "";
  const years = Object.entries(asset.dividends_by_year ?? {}).sort(([a], [b]) => a.localeCompare(b));
  const maxDiv = Math.max(1, ...years.map(([, v]) => v));

  return (
    <main className="page">
      <button className="link-button" onClick={() => navigate(-1)}>
        ← voltar
      </button>

      <div className="asset-head">
        <div>
          <h1 className="page-title" style={{ margin: 0 }}>{asset.ticker}</h1>
          <p className="muted" style={{ margin: 0 }}>
            {asset.name ?? asset.sector ?? asset.asset_class} · {asset.asset_class}
            {asset.sector ? ` · ${asset.sector}` : ""}
          </p>
        </div>
        <div className="asset-head-right">
          {asset.price != null && <strong className="asset-price">{money(asset.price)}</strong>}
          <span className={`risk-seal ${riskClass}`}>{RISK_LABEL[analysis.risk_level ?? "verde"]}</span>
        </div>
      </div>

      {asset.stale && <div className="banner banner-warn">⏳ Dados de cache, possivelmente defasados.</div>}

      {legado && (
        <CeilingBadge
          ceiling={analysis.bazin_ceiling_price}
          price={asset.price}
          margin={analysis.bazin_margin}
          belowCeiling={analysis.bazin_below_ceiling}
          variant="block"
        />
      )}

      {(analysis.highlights ?? []).length > 0 && (
        <ul className="card-reasons">
          {(analysis.highlights ?? []).map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      )}
      {(analysis.red_flags ?? []).length > 0 && (
        <ul className="card-flags">
          {(analysis.red_flags ?? []).map((r, i) => (
            <li key={i}><Icon name="alert" size={13} /> {r}</li>
          ))}
        </ul>
      )}

      <AssetLabels ticker={asset.ticker} assetClass={asset.asset_class} />

      {legado && (
        <>
        <div className="alloc">
          <h3>Fundamentos</h3>
          <div className="fund-grid">
            <Fund label="P/L" value={f.pl != null ? f.pl.toFixed(2) : null} />
            <Fund label="P/VP" value={f.pvp != null ? f.pvp.toFixed(2) : null} />
            {f.dividend_yield != null && (
              <div className="fund-item">
                <Tooltip metricKey="net_yield">
                  <span className="muted">Dividend Yield</span>
                </Tooltip>
                <strong>
                  {pct(f.dividend_yield)} <span className="muted" style={{ fontWeight: 400 }}>bruto</span>
                </strong>
                {f.dividend_yield_net != null && (
                  <span className="muted" style={{ fontSize: 12 }}>
                    {pct(f.dividend_yield_net)} líquido
                  </span>
                )}
              </div>
            )}
            <Fund label="LPA" value={f.lpa != null ? f.lpa.toFixed(2) : null} />
            <Fund label="VPA" value={f.vpa != null ? f.vpa.toFixed(2) : null} />
            <Fund label="ROE" value={f.roe != null ? pct(f.roe) : null} />
            <Fund label="Margem líquida" value={f.net_margin != null ? pct(f.net_margin) : null} />
            <Fund label="Dív. líq./EBIT (proxy)" value={f.net_debt_to_ebitda != null ? f.net_debt_to_ebitda.toFixed(2) : null} />
            <Fund label="Liquidez corrente" value={f.current_ratio != null ? f.current_ratio.toFixed(2) : null} />
          </div>
          <p className="muted" style={{ fontSize: 12, marginBottom: 0 }}>Fonte: {asset.source}</p>
        </div>

        <YocEvolution ticker={asset.ticker} />

        {years.length > 0 && (
          <div className="alloc">
            <h3>Proventos por ano</h3>
            <div className="prov-bars">
              {years.map(([y, v]) => (
                <div key={y} className="prov-row">
                  <span className="prov-year">{y}</span>
                  <div className="prov-track">
                    <div className="prov-fill" style={{ width: `${(v / maxDiv) * 100}%` }} />
                  </div>
                  <span className="prov-val">{money(v)}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="alloc">
          <h3>Leitura dos proventos</h3>
          <div className="fund-grid">
            <Fund
              label="Preço-teto de Bazin"
              value={
                analysis.bazin_ceiling_price != null
                  ? `${money(analysis.bazin_ceiling_price)} (DY-alvo ${pct(analysis.bazin_target_yield)})`
                  : null
              }
            />
            <Fund
              label="Consistência dos proventos"
              value={analysis.dividend_consistency != null ? pct(analysis.dividend_consistency, 0) : null}
            />
            <Fund
              label="Crescimento dos proventos"
              value={
                analysis.dividend_cagr != null
                  ? `${analysis.dividend_cagr > 0 ? "+" : ""}${pct(analysis.dividend_cagr)} a.a.`
                  : null
              }
            />
            <Fund
              label="Payout (provento médio ÷ LPA)"
              value={analysis.payout_ratio != null ? pct(analysis.payout_ratio, 0) : null}
            />
          </div>
          <p className="muted" style={{ fontSize: 12, marginBottom: 0 }}>
            Campo vazio: a fonte não trouxe o dado.
          </p>
        </div>
        </>
      )}

      {!legado && (
        <p className="muted asset-sem-metricas">
          {classLabel(asset.asset_class)} não tem preço-teto, Yield on Cost nem fundamentos
          de empresa: essas contas partem de lucro e histórico de dividendo de uma companhia.
          O que dirige a compra aqui é o peso na carteira alvo —{" "}
          <Link to="/alvo">ver no Alvo →</Link>
        </p>
      )}

    </main>
  );
}
