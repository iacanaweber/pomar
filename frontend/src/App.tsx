import { useEffect, useState } from "react";
import { api } from "./api/client";
import type { Glossary } from "./types";
import { GlossaryContext } from "./hooks/useGlossary";
import { PlanPage } from "./pages/PlanPage";

export default function App() {
  const [glossary, setGlossary] = useState<Glossary>({});

  useEffect(() => {
    api.glossary().then(setGlossary).catch(() => {});
  }, []);

  return (
    <GlossaryContext.Provider value={glossary}>
      <header className="header">
        <div className="brand">
          <span className="logo">🌳</span>
          <div>
            <h1>Pomar</h1>
            <p>Plante seus aportes, colha dividendos.</p>
          </div>
        </div>
      </header>
      <PlanPage />
      <footer className="footer">
        Pomar · dados de mercado por brapi.dev · carteira via Ghostfolio · conteúdo educativo
      </footer>
    </GlossaryContext.Provider>
  );
}
