import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { usePreferences, useSavePreferences } from "../api/queries";
import { HealthBanner } from "./HealthBanner";
import { parseBRL } from "../lib/format";

const KEY = "pomar-onboarding-done";

function isDone(): boolean {
  try {
    return localStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}

/**
 * Onboarding leve (2-3 passos), mostrado no 1º acesso quando ainda não há meta de renda.
 * Reusa o HealthBanner para o passo "conectar carteira". Dispensável e não-repetível.
 */
export function Onboarding() {
  const prefs = usePreferences();
  const savePrefs = useSavePreferences();
  const [dismissed, setDismissed] = useState(isDone());
  const [meta, setMeta] = useState("");

  const hasTarget = (prefs.data?.target_monthly_income ?? 0) > 0;
  // só aparece se ainda não definiu meta E não foi dispensado
  if (dismissed || hasTarget || !prefs.data) return null;

  const finish = () => {
    try {
      localStorage.setItem(KEY, "1");
    } catch {
      /* ignora */
    }
    setDismissed(true);
  };

  const saveMeta = (e: FormEvent) => {
    e.preventDefault();
    const value = parseBRL(meta);
    if (!(value > 0)) return;
    savePrefs.mutate({ target_monthly_income: value }, { onSuccess: finish });
  };

  return (
    <section className="onboarding alloc" aria-label="Primeiros passos no Pomar">
      <div className="onboarding-head">
        <h3 style={{ margin: 0 }}>🌱 Bem-vindo ao Pomar — 3 passos rápidos</h3>
        <button className="link-button" onClick={finish}>
          pular
        </button>
      </div>

      <ol className="onboarding-steps">
        <li>
          <strong>1. Conecte sua carteira</strong>
          <HealthBanner />
          <p className="muted" style={{ margin: "4px 0 0", fontSize: 13 }}>
            Sem Ghostfolio conectado o plano segue mirando suas metas com carteira vazia.
          </p>
        </li>
        <li aria-current="step">
          <strong>2. Defina sua meta de renda mensal</strong>
          <form className="onboarding-meta" onSubmit={saveMeta}>
            <div className="money">
              <span>R$</span>
              <input
                inputMode="decimal"
                placeholder="ex.: 5.000"
                value={meta}
                onChange={(e) => setMeta(e.target.value)}
              />
            </div>
            <button className="primary" type="submit" disabled={savePrefs.isPending || !(parseBRL(meta) > 0)}>
              {savePrefs.isPending ? "Salvando…" : "Salvar meta"}
            </button>
          </form>
        </li>
        <li>
          <strong>3. Veja seu primeiro plano</strong>
          <p style={{ margin: "4px 0 0" }}>
            <Link to="/plano" className="asset-link" onClick={finish}>
              Ir para o plano →
            </Link>
          </p>
        </li>
      </ol>
    </section>
  );
}
