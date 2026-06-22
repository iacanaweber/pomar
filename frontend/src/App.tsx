import { Navigate, NavLink, Route, Routes } from "react-router-dom";
import { useAuthStatus, useLogout } from "./api/queries";
import { GlossaryProvider } from "./app/GlossaryProvider";
import { AssetPage } from "./pages/AssetPage";
import { IncomePage } from "./pages/IncomePage";
import { LoginPage } from "./pages/LoginPage";
import { PlanPage } from "./pages/PlanPage";
import { PortfolioPage } from "./pages/PortfolioPage";

function AppShell() {
  const logout = useLogout();
  return (
    <>
      <header className="header">
        <div className="brand">
          <span className="logo">🌳</span>
          <div>
            <h1>Pomar</h1>
            <p>Plante seus aportes, colha dividendos.</p>
          </div>
          <button className="header-action" onClick={() => logout.mutate()}>
            Sair
          </button>
        </div>
      </header>

      <nav className="tabs">
        <NavLink to="/plano" className={({ isActive }) => `tab ${isActive ? "tab-on" : ""}`}>
          Recomendações
        </NavLink>
        <NavLink to="/carteira" className={({ isActive }) => `tab ${isActive ? "tab-on" : ""}`}>
          Minha carteira
        </NavLink>
        <NavLink to="/renda" className={({ isActive }) => `tab ${isActive ? "tab-on" : ""}`}>
          Renda passiva
        </NavLink>
      </nav>

      <Routes>
        <Route path="/plano" element={<PlanPage />} />
        <Route path="/carteira" element={<PortfolioPage />} />
        <Route path="/renda" element={<IncomePage />} />
        <Route path="/ativo/:ticker" element={<AssetPage />} />
        <Route path="*" element={<Navigate to="/plano" replace />} />
      </Routes>

      <footer className="footer">
        Pomar · dados por Fundamentus, StatusInvest e brapi · carteira via Ghostfolio · conteúdo
        educativo
      </footer>
    </>
  );
}

export default function App() {
  const auth = useAuthStatus();
  if (auth.isLoading) {
    return (
      <main className="page">
        <p className="muted">Carregando…</p>
      </main>
    );
  }
  if (auth.data?.auth_required && !auth.data.authenticated) {
    return <LoginPage />;
  }
  return (
    <GlossaryProvider>
      <AppShell />
    </GlossaryProvider>
  );
}
