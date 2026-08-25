/** Registro do service worker, com o estado EXPOSTO em vez de engolido.
 *
 *  O GAIA registra com `.catch(() => {})`. Servido em `http://<ip-da-lan>:3334` — que é
 *  como os dois apps rodam — o registro FALHA, porque service worker exige contexto
 *  seguro. O catch vazio faz parecer que o SW está ativo quando não está, e o sintoma
 *  aparece meses depois como "o app não abre sem internet".
 *
 *  Nada disso impede instalar nem o modo standalone, que é o que o usuário quer. O que
 *  muda é o que ele não tem: shell offline, Web Push, e o que o Chrome cria é um atalho
 *  em vez de um WebAPK. Por isso o estado vira dado na tela, não silêncio.
 */

export type SwState =
  | 'unsupported' // o navegador não tem service worker
  | 'insecure' // origem sem HTTPS (nem localhost): o registro nem é tentado
  | 'dev' // build de desenvolvimento — não registramos de propósito
  | 'active' // registrado e no ar
  | 'failed' // tentou registrar e falhou

export interface PwaStatus {
  state: SwState
  /** Uma versão nova está esperando para assumir (ver `applyUpdate`). */
  updateReady: boolean
  error?: string
}

type Listener = (status: PwaStatus) => void

let status: PwaStatus = { state: 'unsupported', updateReady: false }
const listeners = new Set<Listener>()

const emit = (next: Partial<PwaStatus>) => {
  status = { ...status, ...next }
  listeners.forEach((l) => l(status))
}

export const getPwaStatus = (): PwaStatus => status

export function subscribePwa(listener: Listener): () => void {
  listeners.add(listener)
  listener(status)
  return () => listeners.delete(listener)
}

/** Manda o SW em espera assumir. Só é chamado quando o usuário aceita a atualização —
 *  trocar o app por baixo dele no meio de um aporte seria o pior momento possível. */
export function applyUpdate(): void {
  navigator.serviceWorker?.getRegistration().then((reg) => {
    if (reg?.waiting) {
      reg.waiting.postMessage('skip-waiting')
      // recarrega quando o novo assumir de fato
      navigator.serviceWorker.addEventListener('controllerchange', () => location.reload(), {
        once: true,
      })
    }
  })
}

export function registerServiceWorker(): void {
  if (!import.meta.env.PROD) {
    emit({ state: 'dev' })
    return
  }
  if (!('serviceWorker' in navigator)) {
    emit({ state: 'unsupported' })
    return
  }
  // `isSecureContext` cobre HTTPS e localhost — exatamente a condição do SW.
  if (!window.isSecureContext) {
    emit({ state: 'insecure' })
    console.info(
      '[Pomar] Service worker não registrado: a origem não é segura (HTTPS ou localhost). ' +
        'A instalação e o modo standalone seguem funcionando; o que falta é cache offline e Web Push.',
    )
    return
  }

  window.addEventListener('load', () => {
    navigator.serviceWorker
      .register('/sw.js')
      .then((reg) => {
        emit({ state: 'active', updateReady: !!reg.waiting })
        reg.addEventListener('updatefound', () => {
          const novo = reg.installing
          novo?.addEventListener('statechange', () => {
            // 'installed' + já existe controlador = versão nova esperando, não 1ª instalação
            if (novo.state === 'installed' && navigator.serviceWorker.controller) {
              emit({ updateReady: true })
            }
          })
        })
      })
      .catch((err: unknown) => {
        const error = err instanceof Error ? err.message : String(err)
        emit({ state: 'failed', error })
        console.info('[Pomar] Falha ao registrar o service worker:', error)
      })
  })
}
