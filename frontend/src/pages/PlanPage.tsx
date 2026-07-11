import { useState } from "react";
import { ApiError } from "../api/client";
import { usePlan, usePlanLatest, usePreferences, useStrategies } from "../api/queries";
import { CLASS_LABEL, PlanControls } from "../components/PlanControls";
import { RankedList } from "../components/RankedList";
import { AllocationSummary } from "../components/AllocationSummary";
import { HealthBanner } from "../components/HealthBanner";
import { OrdersHistory } from "../components/OrdersHistory";
import { ReserveSummaryCard } from "../components/ReserveSummaryCard";
import type { PlanRequest } from "../types";
import { shortDateTime } from "../lib/format";

export function PlanPage() {
  const strategies = useStrategies();
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
        strategies={strategies.data ?? null}
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
          {result.focus && result.focus !== "BALANCE" && (
            <p className="muted plan-restored">
              🎯 Plano focado em {CLASS_LABEL[result.focus] ?? result.focus} — todo o aporte
              de renda variável foi para essa classe.
            </p>
          )}
          {(result.warnings ?? []).length > 0 && (
            <div className="banner banner-warn">
              {(result.warnings ?? []).map((w, i) => (
                <div key={i}>• {w}</div>
              ))}
            </div>
          )}
          {result.reserve && (
            <ReserveSummaryCard reserve={result.reserve} currency={result.currency} />
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
