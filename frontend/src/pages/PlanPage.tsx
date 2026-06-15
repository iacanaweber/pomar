import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { PlanResponse, StrategiesResponse } from "../types";
import { PlanControls } from "../components/PlanControls";
import { RankedList } from "../components/RankedList";
import { AllocationSummary } from "../components/AllocationSummary";

export function PlanPage() {
  const [strategies, setStrategies] = useState<StrategiesResponse | null>(null);
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.strategies().then(setStrategies).catch(() => {});
  }, []);

  const run = async (aporte: number, strategy: string) => {
    setLoading(true);
    setError(null);
    try {
      setPlan(await api.plan({ aporte, strategy }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao gerar o plano");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="page">
      <PlanControls strategies={strategies} loading={loading} onSubmit={run} />

      {error && <div className="banner banner-error">⚠️ {error}</div>}

      {plan && (
        <>
          {plan.warnings.length > 0 && (
            <div className="banner banner-warn">
              {plan.warnings.map((w, i) => (
                <div key={i}>• {w}</div>
              ))}
            </div>
          )}
          <AllocationSummary plan={plan} />
          <RankedList plan={plan} />
          <p className="disclaimer">{plan.disclaimer}</p>
        </>
      )}
    </main>
  );
}
