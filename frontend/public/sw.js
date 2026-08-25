/* Pomar service worker — shell precache + cache-on-fetch de assets.

   /api/ NUNCA passa por aqui. Dado financeiro servido de cache em silêncio é pior que
   app que não abre: um saldo velho parece um saldo, e a decisão de aporte sai errada
   sem nada avisar.

   O SW só é registrado em contexto seguro (HTTPS ou localhost). Servido em
   http://<ip-da-lan>:3334 ele nem chega a instalar — ver o registro em main.tsx, que
   diz isso em voz alta em vez de engolir o erro. O arquivo fica versionado e pronto
   para passar a valer sozinho no dia em que houver TLS.
*/
const VERSION = 'pomar-v1'
const SHELL = ['/', '/manifest.webmanifest', '/favicon.svg', '/icons/icon-192.png', '/icons/icon-512.png']

self.addEventListener('install', (e) => {
  // Sem skipWaiting: um SW novo assumindo no meio de um aporte trocaria o app por baixo
  // do usuário. Ele espera, avisa a página, e só assume quando ela mandar (ver 'message').
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL)))
})

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  )
})

// A página pede a troca quando o usuário aceita a nova versão.
self.addEventListener('message', (e) => {
  if (e.data === 'skip-waiting') self.skipWaiting()
})

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url)
  if (e.request.method !== 'GET' || url.origin !== location.origin) return
  if (url.pathname.startsWith('/api/')) return // dados nunca passam pelo SW

  // Navegação: network-first com fallback ao shell cacheado (offline).
  if (e.request.mode === 'navigate') {
    e.respondWith(
      fetch(e.request)
        .then((res) => {
          const copy = res.clone()
          caches.open(VERSION).then((c) => c.put('/', copy))
          return res
        })
        .catch(() => caches.match('/').then((hit) => hit || Response.error())),
    )
    return
  }

  // Assets com hash no nome: cache-first, alimentado no primeiro fetch. O hash é o que
  // torna isso seguro — um asset novo tem outro nome e nunca colide com o cacheado.
  if (url.pathname.startsWith('/assets/') || url.pathname.startsWith('/icons/')) {
    e.respondWith(
      caches.match(e.request).then(
        (hit) =>
          hit ||
          fetch(e.request).then((res) => {
            const copy = res.clone()
            caches.open(VERSION).then((c) => c.put(e.request, copy))
            return res
          }),
      ),
    )
  }
})
