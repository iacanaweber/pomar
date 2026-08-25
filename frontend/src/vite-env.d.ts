/// <reference types="vite/client" />
// Traz os tipos de `import.meta.env` (usado em lib/pwa.ts para registrar o service
// worker só em produção). Sem esta referência o `tsc -b` não conhece `import.meta.env`.
