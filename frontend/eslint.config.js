import js from "@eslint/js";
import globals from "globals";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";

// Havia dois comentários `eslint-disable-next-line` num projeto sem ESLint instalado,
// sem config e sem script. Agora eles significam algo — e as regras abaixo pegam
// automaticamente a categoria de sedimento que estava sendo limpa à mão: import morto,
// export sem consumidor, dependência de hook mal declarada.
export default tseslint.config(
  { ignores: ["dist", "node_modules", "src/api/schema.d.ts"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["src/**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
      // Argumento não usado com prefixo _ é intencional; o resto é sedimento.
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      // `console.warn`/`error` são legítimos no ErrorBoundary; `console.log` é resto de
      // depuração.
      "no-console": ["warn", { allow: ["warn", "error"] }],
      // Rebaixada de propósito. A regra acusa os três usos do padrão "sincronizar estado
      // externo com estado local uma vez": a trava de hidratação do formulário de aporte,
      // o toast que dispara quando a prop muda, e o deep-link #CLASSE que abre a sanfona
      // em /alvo. Nos três o efeito É a sincronização com algo de fora do React, que é
      // exatamente para o que efeito serve. Deixar como erro faria a regra ser desligada
      // por inteiro na primeira vez que atrapalhasse — pior resultado.
      "react-hooks/set-state-in-effect": "warn",
    },
  },
  {
    // Scripts de autoria (gen-icons, css-audit, font-charset): Node, não navegador.
    files: ["scripts/**/*.mjs", "*.config.{js,ts}"],
    languageOptions: { globals: globals.node },
  },
);
