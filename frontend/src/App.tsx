import { useEffect, useState } from "react";
import { api } from "./api/client";
import type { Glossary } from "./types";
import { GlossaryContext } from "./hooks/useGlossary";
import { PlanPage } from "./pages/PlanPage";
import { PortfolioPage } from "./pages/PortfolioPage";

type Tab = "plan" | "portfolio";

export default function App() {
  const [glossary, setGlossary] = useState<Glossary>({});
  const [tab, setTab] = useState<Tab>("plan");

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

      <nav className="tabs">
        <button className={`tab ${tab === "plan" ? "tab-on" : ""}`} onClick={() => setTab("plan")}>
          Recomendações
        </button>
        <button
          className={`tab ${tab === "portfolio" ? "tab-on" : ""}`}
          onClick={() => setTab("portfolio")}
        >
          Minha carteira
        </button>
      </nav>

      {tab === "plan" ? <PlanPage /> : <PortfolioPage />}

      <footer className="footer">
        Pomar · dados de mercado por brapi.dev · carteira via Ghostfolio · conteúdo educativo
      </footer>
    </GlossaryContext.Provider>
  );
}
