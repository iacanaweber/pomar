import { applyUpdate } from "../lib/pwa";
import { usePwa } from "../hooks/usePwa";

/** Aviso de nova versão. Uma linha e um botão — a troca só acontece se o usuário mandar.
 *
 *  Recarregar por baixo dele no meio de um aporte é o pior momento possível para o app
 *  se atualizar: o formulário some com o valor digitado e o plano na tela deixa de
 *  corresponder ao que ele estava lendo. Por isso o `sw.js` não usa `skipWaiting` na
 *  instalação, e a decisão vem daqui. */
export function UpdateBanner() {
  const { updateReady } = usePwa();
  if (!updateReady) return null;
  return (
    <div className="banner update-banner" role="status">
      <span>Nova versão disponível.</span>
      <button className="link-button" onClick={applyUpdate}>
        Atualizar agora
      </button>
    </div>
  );
}
