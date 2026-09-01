import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// O Vitest rodava em defaults: ambiente `node`, sem setup, sem DOM. Por isso os cinco
// testes que existiam cobriam só funções puras — não havia como renderizar um componente.
// Os caminhos que mais precisavam de teste (mutação que falha em silêncio, estado vazio)
// eram exatamente os inalcançáveis.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    globals: false, // `describe`/`it` continuam importados explicitamente, como já eram
    include: ["src/**/*.test.{ts,tsx}"],
    restoreMocks: true,
  },
});
