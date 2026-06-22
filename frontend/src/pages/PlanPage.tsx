import { ApiError } from "../api/client";
import { usePlan, usePreferences, useStrategies } from "../api/queries";
import { PlanControls } from "../components/PlanControls";
import { RankedList } from "../components/RankedList";
import { AllocationSummary } from "../components/AllocationSummary";
import { HealthBanner } from "../components/HealthBanner";

export function PlanPage() {
  const strategies = useStrategies();
  const preferences = usePreferences();
  const plan = usePlan();
  const result = plan.data;

  return (
    <main className="page">
      <HealthBanner />

      <PlanControls
        strategies={strategies.data ?? null}
        preferences={preferences.data}
        loading={plan.isPending}
        onSubmit={(req) => plan.mutate(req)}
      />

      {plan.isError && (
        <div className="banner banner-error">
          ⚠️ {plan.error instanceof ApiError ? plan.error.userMessage : "Erro ao gerar o plano"}
        </div>
      )}

      {result && (
        <>
          {(result.warnings ?? []).length > 0 && (
            <div className="banner banner-warn">
              {(result.warnings ?? []).map((w, i) => (
                <div key={i}>• {w}</div>
              ))}
            </div>
          )}
          <AllocationSummary plan={result} />
          <RankedList plan={result} />
          <p className="disclaimer">{result.disclaimer}</p>
        </>
      )}
    </main>
  );
}
