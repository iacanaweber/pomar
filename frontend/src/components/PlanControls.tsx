import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import type { PlanRequest, Preferences } from "../types";
import { useSavePreferences } from "../api/queries";
import { ALLOCATION_CLASSES, byWeightDesc, CLASS_LABEL, INVESTABLE_CLASSES } from "../lib/classes";
import { parseBRL } from "../lib/format";
import type { SwState } from "../lib/pwa";
import { usePwa } from "../hooks/usePwa";
import { SavedToast } from "./SavedToast";
import { Tooltip } from "./Tooltip";
import { Icon } from "./Icon";

interface Props {
  preferences?: Preferences;
  loading: boolean;
  onSubmit: (req: PlanRequest) => void;
}

/** Aporte assumido quando o campo fica vazio — só para VER as recomendações. */
const APORTE_PADRAO = 2000;

/** Uma linha, sem prosa: o usuário precisa saber se tem cache offline sem abrir o
 *  DevTools. Em `http://<ip-da-lan>` o service worker não registra, e sem esta linha o
 *  app parecia ter offline que nunca teve. */
const SW_LABEL: Record<SwState, string> = {
  active: "Cache offline ativo",
  insecure: "Sem cache offline (precisa de HTTPS)",
  unsupported: "Sem cache offline (navegador não suporta)",
  failed: "Sem cache offline (falha ao registrar)",
  dev: "Sem cache offline (modo de desenvolvimento)",
};

function OfflineStatusLine() {
  const { state } = usePwa();
  return (
    <span className="muted sw-status">
      {state === "active" ? "●" : "○"} {SW_LABEL[state]}
    </span>
  );
}

export function PlanControls({ preferences, loading, onSubmit }: Props) {
  const [aporte, setAporte] = useState("");
  const [touched, setTouched] = useState(false);
  const [advanced, setAdvanced] = useState(false);
  // Classes marcadas para ESTE aporte. Começa com todas: a escolha é do momento
  // ("hoje só quero FII"), não uma configuração — por isso não é persistida.
  const [selected, setSelected] = useState<string[]>([...INVESTABLE_CLASSES]);

  const [minTicket, setMinTicket] = useState("100");

  const savePrefs = useSavePreferences();
  const [savedAt, setSavedAt] = useState<number | null>(null);

  // Sincroniza o formulário com as preferências salvas quando elas chegam (uma vez).
  useEffect(() => {
    if (!preferences) return;
    setMinTicket(String(preferences.min_ticket));
    if (preferences.aporte_default) setAporte(String(preferences.aporte_default));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preferences]);

  const blank = aporte.trim() === "";
  const baskets = preferences?.class_targets ?? {};
  const targets = preferences?.targets ?? {};
  const sizeOf = (cls: string) => Object.keys(baskets[cls] ?? {}).length;
  const hasAnyBasket = INVESTABLE_CLASSES.some((c) => sizeOf(c) > 0);
  const usable = selected.filter((c) => sizeOf(c) > 0);

  const toggle = (cls: string) =>
    setSelected((s) => (s.includes(cls) ? s.filter((c) => c !== cls) : [...s, cls]));

  const buildRequest = (): PlanRequest | null => {
    // Campo vazio simula com o valor padrão — ver o plano não deve custar uma digitação
    // toda vez. Texto NÃO vazio e inválido continua sendo erro: um "2.00o" digitado errado
    // virando um plano silencioso de R$ 2.000 seria pior do que não gerar plano nenhum.
    const value = blank ? APORTE_PADRAO : parseBRL(aporte);
    if (!(value > 0)) return null;
    return {
      aporte: value,
      classes: selected,
      min_ticket: parseBRL(minTicket) || 0,
      allow_empty_portfolio: false, // fail-closed: sem carteira, o plano é abortado
    };
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setTouched(true);
    const req = buildRequest();
    if (req) onSubmit(req);
  };

  const savePreferences = () => {
    savePrefs.mutate(
      {
        min_ticket: parseBRL(minTicket) || 0,
        ...(parseBRL(aporte) > 0 ? { aporte_default: parseBRL(aporte) } : {}),
      },
      { onSuccess: () => setSavedAt(Date.now()) },
    );
  };

  const valueInvalid = touched && !blank && !(parseBRL(aporte) > 0);
  // ALLOCATION_CLASSES, e não INVESTABLE_CLASSES: a linha se chama "meta da CARTEIRA" e a
  // renda fixa é uma classe dela como qualquer outra. Com a lista dos investáveis, uma
  // carteira 50% em renda fixa exibia "5% FIIs · 45% ETFs" — sem somar 100%.
  const metaLine = byWeightDesc(ALLOCATION_CLASSES, (c) => targets[c] ?? 0)
    .filter((c) => (targets[c] ?? 0) > 0)
    .map((c) => `${Math.round((targets[c] ?? 0) * 100)}% ${CLASS_LABEL[c]}`)
    .join(" · ");

  return (
    <form className="controls" onSubmit={submit}>
      <SavedToast show={savedAt} />

      <label className="field">
        <span>Aporte</span>
        <div className={`money ${valueInvalid ? "money-invalid" : ""}`}>
          <span>R$</span>
          <input
            inputMode="decimal"
            placeholder="2000"
            value={aporte}
            onChange={(e) => setAporte(e.target.value)}
            autoFocus
          />
        </div>
        {valueInvalid && <span className="field-error">Informe um valor maior que zero.</span>}
      </label>

      {hasAnyBasket ? (
        <fieldset className="class-picker">
          <legend>Aportar em</legend>
          <div className="class-chips">
            {INVESTABLE_CLASSES.map((cls) => {
              const n = sizeOf(cls);
              const on = selected.includes(cls);
              return (
                <label key={cls} className={`class-chip ${on ? "class-chip-on" : ""}`}>
                  <input type="checkbox" checked={on} onChange={() => toggle(cls)} />
                  <span className="class-chip-name">{CLASS_LABEL[cls]}</span>
                  {n > 0 ? (
                    <span className="class-chip-meta">{n} ativos</span>
                  ) : (
                    <span className="class-chip-meta warn">sem composição</span>
                  )}
                </label>
              );
            })}
          </div>
          <p className="muted class-picker-meta">
            {metaLine ? `Meta da carteira: ${metaLine}` : "Sem metas por classe definidas"}
          </p>
          <p className="link-row">
            <Link to="/alvo">Carteira alvo →</Link>
          </p>
        </fieldset>
      ) : (
        <div className="card empty-target">
          <h3>Carteira alvo não definida</h3>
          <p className="muted">O plano precisa de um destino: metas por classe e composição de cada uma.</p>
          <Link className="primary" to="/alvo">
            Montar carteira alvo
          </Link>
        </div>
      )}

      <button
        type="button"
        className="link-button"
        aria-expanded={advanced}
        onClick={() => setAdvanced((v) => !v)}
      >
        <>
          <Icon name="chevron" size={16} /> Ajustes avançados
        </>
      </button>

      {advanced && (
        <div className="advanced">
          <div className="adv-row">
            <label className="field">
              <Tooltip metricKey="min_ticket">
                <span>Ticket mínimo (R$)</span>
              </Tooltip>
              <input
                inputMode="decimal"
                value={minTicket}
                onChange={(e) => setMinTicket(e.target.value)}
              />
            </label>
          </div>
          <span className="muted">Só para abrir posição nova.</span>
          <OfflineStatusLine />
          <button
            type="button"
            className="link-button"
            onClick={savePreferences}
            disabled={savePrefs.isPending}
          >
            {savePrefs.isPending ? "Salvando" : "Salvar padrão"}
          </button>
        </div>
      )}

      <button className="primary" type="submit" disabled={loading || usable.length === 0}>
        {loading ? "Calculando" : "Calcular plano"}
      </button>
      {hasAnyBasket && usable.length === 0 && (
        <span className="field-error">
          Nenhuma classe marcada tem composição. Marque outra ou defina a{" "}
          <Link to="/alvo">carteira alvo</Link>.
        </span>
      )}
    </form>
  );
}
