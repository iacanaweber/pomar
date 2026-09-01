import { useCreateOrder } from "../api/queries";
import { MutationError } from "./MutationError";

/** Fecha o ciclo do aporte: comprou na corretora → um toque registra a execução
 *  (pré-preenchida com a sugestão do plano) e alimenta histórico + disciplina.
 *
 *  Props primitivas em vez de um `PlanAsset`: a compra de um ETF de renda fixa nasce numa
 *  linha do cartão de renda fixa, que não tem — nem precisa ter — o objeto do ranking. */
export function RegisterBuyButton({
  ticker,
  assetClass,
  shares,
  price,
  planId,
}: {
  ticker: string;
  assetClass?: string | null;
  shares: number;
  price?: number | null;
  planId?: number | null;
}) {
  const create = useCreateOrder();
  if (create.isSuccess) return <span className="order-registered">✓ compra registrada</span>;
  return (
    <>
      <button
        className="link-button order-register"
        disabled={create.isPending}
        onClick={(e) => {
          e.stopPropagation();
          create.mutate({
            ticker,
            asset_class: assetClass ?? "STOCK",
            shares,
            price: price ?? 0,
            fees: 0,
            plan_id: planId ?? null,
            note: "registrado do plano",
          });
        }}
      >
        {create.isPending ? "Registrando" : "Registrar compra"}
      </button>
      {/* Sem isto, uma falha ficava idêntica a não ter clicado. */}
      <MutationError error={create.error} acao={`registrar a compra de ${ticker}`} />
    </>
  );
}
