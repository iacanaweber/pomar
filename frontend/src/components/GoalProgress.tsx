import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useIncomeGoal, useNextBuy, usePreferences, useSavePreferences, useStrategies } from "../api/queries";
import type { IncomeGoalResponse, Preferences } from "../types";
import { money, parseBRL, pct } from "../lib/format";
import { SavedToast } from "./SavedToast";
import { Tooltip } from "./Tooltip";

/** "Próximo melhor aporte" — usa a ESTRATÉGIA e os parâmetros salvos (cacheado). */
function NextBuyCard({ prefs }: { prefs?: Preferences }) {
  const plan = useNextBuy(prefs);
  const strategies = useStrategies();

  if (plan.isLoading) return <p className="muted" style={{ margin: "8px 0 0" }}>Buscando o próximo melhor aporte…</p>;
  const first = (plan.data?.ranking ?? []).find((a) => a.suggested);
  if (!first || !first.suggested) {
    return (
      <p className="strategy-desc" style={{ margin: "8px 0 0" }}>
        <Link to="/plano" className="asset-link">Ver plano completo →</Link>
      </p>
    );
  }
  const s = first.suggested;
  const stratLabel =
    (prefs && strategies.data?.presets?.[prefs.strategy]?.label) || prefs?.strategy || "";
  return (
    <div className="goal-nextbuy">
      <span>
        ➜ Próximo melhor aporte: <strong>{first.ticker}</strong> {money(s.invested_exact)}{" "}
        <span className="muted">({s.shares} × {s.price ? money(s.price) : "—"})</span>
        {stratLabel && <span className="muted"> · segundo sua estratégia {stratLabel}</span>}
      </span>
      <Link to="/plano" className="asset-link">Ver plano completo →</Link>
    </div>
  );
}

function ProgressBar({ goal }: { goal: IncomeGoalResponse }) {
  const pctNum = Math.min(Math.round(goal.pct_achieved * 100), 100);
  const achieved = goal.pct_achieved >= 1;
  return (
    <div
      className="goal-bar"
      role="progressbar"
      aria-valuenow={pctNum}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={`Meta de renda: ${pctNum}% atingido`}
    >
      <div className="alloc-track" style={{ height: 18 }}>
        <div
          className="alloc-cur"
          style={{ width: `${pctNum}%`, background: achieved ? "var(--green)" : "var(--leaf)" }}
        />
      </div>
      <span className="goal-bar-label">{pctNum}% atingido</span>
    </div>
  );
}

export function GoalProgress() {
  const { data: goal, isLoading } = useIncomeGoal();
  const prefs = usePreferences();
  const savePrefs = useSavePreferences();
  const [editing, setEditing] = useState(false);
  const [metaInput, setMetaInput] = useState("");
  const [savedAt, setSavedAt] = useState<number | null>(null);

  const target = goal?.target_monthly_income ?? 0;
  const hasTarget = target > 0;

  useEffect(() => {
    if (hasTarget) setMetaInput(String(Math.round(target)));
  }, [hasTarget, target]);

  const saveMeta = (e: FormEvent) => {
    e.preventDefault();
    const value = parseBRL(metaInput);
    if (!(value > 0)) return;
    savePrefs.mutate(
      { target_monthly_income: value },
      {
        onSuccess: () => {
          setEditing(false);
          setSavedAt(Date.now());
        },
      },
    );
  };

  if (isLoading) return <p className="muted">Calculando seu objetivo de renda…</p>;

  const achieved = !!goal && goal.pct_achieved >= 1;

  return (
    <div className="alloc goal-card">
      <SavedToast show={savedAt} message="✓ Meta salva" />
      <div className="goal-head">
        <Tooltip metricKey="income_target">
          <h3 style={{ margin: 0 }}>Objetivo de renda</h3>
        </Tooltip>
        {hasTarget && !editing && (
          <button className="link-button" onClick={() => setEditing(true)}>
            editar
          </button>
        )}
      </div>

      {!hasTarget && !editing && (
        <div className="goal-empty">
          <p className="muted" style={{ marginTop: 0 }}>
            Defina quanto quer receber por mês de dividendos — vamos mostrar o quanto falta e o que
            comprar para chegar lá.
          </p>
          <button className="primary" onClick={() => setEditing(true)}>
            Definir minha meta de renda
          </button>
        </div>
      )}

      {editing && (
        <form className="goal-edit" onSubmit={saveMeta}>
          <label className="field">
            <span>Meta de renda mensal (R$)</span>
            <div className="money">
              <span>R$</span>
              <input
                inputMode="decimal"
                placeholder="ex.: 5.000"
                value={metaInput}
                onChange={(e) => setMetaInput(e.target.value)}
                autoFocus
              />
            </div>
          </label>
          <div className="reserve-actions">
            <button className="primary" type="submit" disabled={savePrefs.isPending || !(parseBRL(metaInput) > 0)}>
              {savePrefs.isPending ? "Salvando…" : "Salvar meta"}
            </button>
            {hasTarget && (
              <button className="link-button" type="button" onClick={() => setEditing(false)}>
                Cancelar
              </button>
            )}
          </div>
        </form>
      )}

      {hasTarget && !editing && goal && (
        <>
          <p className="goal-target">
            Meta: <strong>{money(target, goal.currency)}/mês</strong>
          </p>
          <ProgressBar goal={goal} />
          {achieved ? (
            <p className="goal-status risk-verde">
              🎉 Meta atingida! Você recebe {money(goal.current_monthly_income, goal.currency)}/mês.
              Que tal subir a meta?
            </p>
          ) : (
            <p className="goal-status">
              Você recebe <strong>{money(goal.current_monthly_income, goal.currency)}/mês</strong>
              {goal.include_reserve_income && goal.reserve_monthly_income != null && goal.reserve_monthly_income > 0 && (
                <> (+ <strong>{money(goal.reserve_monthly_income, goal.currency)}</strong> da reserva)</>
              )}{" "}
              · faltam <strong>{money(goal.gap_monthly, goal.currency)}/mês</strong>
              {goal.estimated_years_to_goal != null && (
                <>
                  {" "}· em ~{goal.estimated_years_to_goal} {goal.estimated_years_to_goal === 1 ? "ano" : "anos"}
                  {(goal.expected_inflation ?? 0) > 0 ? " (em reais de hoje)" : ""}
                </>
              )}
            </p>
          )}
          {!goal.include_reserve_income && goal.reserve_monthly_income != null && goal.reserve_monthly_income > 0 && !achieved && (
            <p className="muted" style={{ fontSize: 12, margin: "4px 0 0" }}>
              Sua reserva rende ~{money(goal.reserve_monthly_income, goal.currency)}/mês (não conta
              na meta — ative em Plantar → Ajustes avançados se quiser somar).
            </p>
          )}
          {goal.next_milestone != null && goal.milestone_gap != null && !achieved && (
            <p className="goal-milestone">
              🎯 Próximo marco: <strong>{money(goal.next_milestone, goal.currency)}/mês</strong> — faltam{" "}
              {money(goal.milestone_gap, goal.currency)} de renda
              {goal.milestone_capital_needed != null && (
                <> (≈ {money(goal.milestone_capital_needed, goal.currency)} investidos ao seu yield)</>
              )}
            </p>
          )}
          {goal.required_monthly_contribution != null && !achieved && (
            <p className="strategy-desc" style={{ marginTop: 4 }}>
              Aportando <strong>{money(goal.required_monthly_contribution, goal.currency)}/mês</strong>{" "}
              por {goal.horizon_years} anos (yield {pct(goal.portfolio_yield)}
              {(goal.expected_inflation ?? 0) > 0 ? `, inflação ${pct(goal.expected_inflation ?? 0)}` : ""}).
            </p>
          )}
          {!achieved && <NextBuyCard prefs={prefs.data} />}
          {(goal.warnings ?? []).map((w, i) => (
            <p key={i} className="muted" style={{ fontSize: 12, margin: "6px 0 0" }}>• {w}</p>
          ))}
        </>
      )}
    </div>
  );
}
