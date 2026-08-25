import { useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/client";
import { usePlan, usePlanLatest, usePreferences } from "../api/queries";
import { PlanControls } from "../components/PlanControls";
import { RankedList } from "../components/RankedList";
import { AllocationSummary } from "../components/AllocationSummary";
import { HealthBanner } from "../components/HealthBanner";
import { OrdersHistory } from "../components/OrdersHistory";
import { FixedIncomeSuggestionCard } from "../components/FixedIncomeSuggestionCard";
import type { PlanRequest } from "../types";
import { classLabel } from "../lib/classes";
import { shortDateTime } from "../lib/format";

export function PlanPage() {
  const preferences = usePreferences();
  const plan = usePlan();
  const latest = usePlanLatest();
  const [lastReq, setLastReq] = useState<PlanRequest | null>(null);

  // Plano recém-gerado tem prioridade; senão, o último plano PERSISTIDO — gerar plano,
  // ir à corretora e voltar não perde mais nada (nem repete o POST de 60s).
  const result = plan.data ?? latest.data;
  const isRestored = !plan.data && !!latest.data;

  const planError = plan.error instanceof ApiError ? plan.error : null;
  const portfolioUnavailable = planError?.status === 503;

  const submit = (req: PlanRequest) => {
    setLastReq(req);
    plan.mutate(req);
  };

  return (
    <main className="page">
      <HealthBanner />

      <PlanControls
        preferences={preferences.data}
        loading={plan.isPending}
        onSubmit={submit}
      />

      {plan.isError && (
        <div className="banner banner-error">
          ⚠️ {planError ? planError.userMessage : "Erro ao gerar o plano"}
          {portfolioUnavailable && lastReq && (
            <div style={{ marginTop: 6 }}>
              <button
                className="link-button"
                onClick={() => plan.mutate({ ...lastReq, allow_empty_portfolio: true })}
              >
                Planejar sem a carteira (ignora posições existentes)
              </button>
            </div>
          )}
        </div>
      )}

      {result && (
        <>
          {isRestored && (
            <p className="muted plan-restored">
              📌 Último plano gerado{result.created_at ? ` em ${shortDateTime(result.created_at)}` : ""} —
              gere um novo se a carteira ou o aporte mudaram.
            </p>
          )}
          {(result.classes_skipped ?? []).length > 0 && (
            <div className="banner banner-warn">
              ⚠️ Sem composição definida:{" "}
              {(result.classes_skipped ?? []).map((c) => classLabel(c)).join(", ")} — essas
              classes ficaram de fora do plano.{" "}
              <Link to={`/alvo#${(result.classes_skipped ?? [])[0]}`}>definir agora →</Link>
            </div>
          )}
          {(result.warnings ?? []).length > 0 && (
            <div className="banner banner-warn">
              {(result.warnings ?? []).map((w, i) => (
                <div key={i}>• {w}</div>
              ))}
            </div>
          )}
          {/* A renda fixa vem PRIMEIRO: é o primeiro degrau da cascata, e a ordem da tela
              é a ordem em que o dinheiro é decidido. */}
          {result.fixed_income && (
            <FixedIncomeSuggestionCard
              suggestion={result.fixed_income}
              reserve={result.reserve}
              currency={result.currency}
            />
          )}
          <AllocationSummary plan={result} />
          <RankedList plan={result} />
          <p className="disclaimer">{result.disclaimer}</p>
        </>
      )}

      <OrdersHistory />
    </main>
  );
}
