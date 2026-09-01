import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/client";
import {
  useFixedIncome,
  usePlan,
  usePlanLatest,
  usePortfolio,
  usePreferences,
} from "../api/queries";
import { PlanControls } from "../components/PlanControls";
import { RankedList } from "../components/RankedList";
import { Canteiro } from "../components/Canteiro";
import { buildComparison } from "../lib/comparison";
import { HealthBanner } from "../components/HealthBanner";
import { OrdersHistory } from "../components/OrdersHistory";
import { FixedIncomeSuggestionCard } from "../components/FixedIncomeSuggestionCard";
import type { PlanRequest } from "../types";
import { classLabel } from "../lib/classes";
import { shortDateTime } from "../lib/format";
import { Icon } from "../components/Icon";

export function PlanPage() {
  const preferences = usePreferences();
  const plan = usePlan();
  const latest = usePlanLatest();
  const portfolio = usePortfolio();
  const fixedIncome = useFixedIncome();
  const [lastReq, setLastReq] = useState<PlanRequest | null>(null);

  // Plano recém-gerado tem prioridade; senão, o último plano PERSISTIDO — gerar plano,
  // ir à corretora e voltar não perde mais nada (nem repete o POST de 60s).
  const result = plan.data ?? latest.data;
  const isRestored = !plan.data && !!latest.data;

  // A MESMA conta que a Carteira faz. Deliberado: o desvio precisa bater entre as duas
  // telas, e `buildComparison` é a única implementação testada dele.
  const comparison = useMemo(
    () =>
      buildComparison(
        portfolio.data?.positions ?? [],
        portfolio.data?.total_value ?? 0,
        preferences.data?.targets ?? {},
        preferences.data?.class_targets ?? {},
        {
          rendaFixaValue: fixedIncome.data?.portfolio_balance ?? 0,
          legacyInTotal: preferences.data?.legacy_in_total ?? true,
        },
      ),
    [portfolio.data, preferences.data, fixedIncome.data],
  );

  // Quanto o plano manda para cada classe — a camada clara em cima do canteiro.
  const aportePorClasse = useMemo(() => {
    if (!result) return undefined;
    const soma: Record<string, number> = {};
    for (const a of result.ranking ?? []) {
      const brl = a.suggested?.invested_exact ?? 0;
      if (brl > 0) soma[a.asset_class] = (soma[a.asset_class] ?? 0) + brl;
    }
    const rf = result.fixed_income?.directed_now ?? 0;
    if (rf > 0) soma.RENDA_FIXA = (soma.RENDA_FIXA ?? 0) + rf;
    return soma;
  }, [result]);

  const planError = plan.error instanceof ApiError ? plan.error : null;
  const portfolioUnavailable = planError?.status === 503;

  const submit = (req: PlanRequest) => {
    setLastReq(req);
    plan.mutate(req);
  };

  return (
    <main className="page">
      <HealthBanner />

      {/* Diagnóstico antes de ação, e agora com um objeto só: o canteiro É a carteira
          alvo, e o vazio de cada cova é a pergunta que o formulário abaixo responde.
          Esta tela não tinha título NENHUM — o primeiro heading era o h2 do RankedList,
          que só existe quando há compras a fazer. */}
      <h1 className="page-title">Plantar</h1>
      {!portfolio.isPending && (
        <Canteiro
          comparison={comparison}
          aporte={aportePorClasse}
          coberturaLegado={result?.legacy?.gap_coverage}
          gapLegado={result?.legacy?.gap}
          moeda={result?.currency}
        />
      )}

      <PlanControls
        preferences={preferences.data}
        preferencesPending={preferences.isPending}
        loading={plan.isPending}
        onSubmit={submit}
      />

      {/* O plano leva até 60 segundos. Sem região viva, quem usa leitor de tela aperta o
          botão e nada mais é anunciado — nem o fim do cálculo. */}
      <p className="sr-only" role="status">
        {plan.isPending ? "Calculando o plano de aporte." : plan.isSuccess ? "Plano pronto." : ""}
      </p>

      {plan.isError && (
        <div className="banner banner-error">
          <Icon name="alert" size={15} />{" "}
          {planError ? planError.userMessage : "Erro ao gerar o plano"}
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
              Último plano{result.created_at ? `, de ${shortDateTime(result.created_at)}` : ""}.
            </p>
          )}
          {(result.classes_skipped ?? []).length > 0 && (
            <div className="banner banner-warn">
              <Icon name="alert" size={15} /> Sem composição definida:{" "}
              {(result.classes_skipped ?? []).map((c) => classLabel(c)).join(", ")} — essas classes
              ficaram de fora do plano.{" "}
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
          {/* O diagnóstico subiu para o canteiro, no topo. Aqui fica só a ação, e dentro
              dela a renda fixa vem antes por ser o primeiro degrau da cascata. */}
          {result.fixed_income && (
            <FixedIncomeSuggestionCard
              suggestion={result.fixed_income}
              reserve={result.reserve}
              currency={result.currency}
              planId={result.plan_id}
            />
          )}
          <RankedList plan={result} />
        </>
      )}

      <OrdersHistory />
    </main>
  );
}
