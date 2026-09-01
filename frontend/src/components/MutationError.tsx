import { ApiError } from "../api/client";
import { Icon } from "./Icon";

/** Aviso de que uma ESCRITA falhou.
 *
 *  O padrão do app era nítido e ruim: leitura tratava falha, escrita quase nunca. Das
 *  catorze mutações, quatro renderizavam erro. As outras dez falhavam em silêncio — o
 *  botão voltava a ficar clicável e nada dizia que não tinha dado certo.
 *
 *  A pior era salvar em /alvo: o usuário equilibrava os pesos até 100%, clicava, e
 *  acreditava ter salvo. Perda de dados sem aviso.
 *
 *  `ErrorBoundary` não cobre nada disso: ele captura throw de RENDER, e o React Query
 *  engole falha de fetch para dentro de `error`.
 *
 *  `role="alert"` porque isto é consequência de uma ação que o usuário acabou de tomar —
 *  ao contrário de um carregamento, que é `status`. */
export function MutationError({
  error,
  acao,
}: {
  error: unknown;
  /** O que falhou, em verbo, do lado do usuário: "salvar as metas", "registrar a compra".
   *  A frase vira "Não foi possível <acao>." */
  acao: string;
}) {
  if (!error) return null;
  const detalhe = error instanceof ApiError ? error.userMessage : null;
  return (
    <p className="mutation-error" role="alert">
      <Icon name="alert" size={14} /> Não foi possível {acao}.{detalhe ? ` ${detalhe}` : ""}
    </p>
  );
}
