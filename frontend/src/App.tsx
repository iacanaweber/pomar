import { Suspense, lazy } from "react";
import { Navigate, NavLink, Route, Routes } from "react-router-dom";
import { useAuthStatus, useLogout } from "./api/queries";
import { GlossaryProvider } from "./app/GlossaryProvider";
import { ThemeToggle } from "./components/ThemeToggle";
import { AssetPage } from "./pages/AssetPage";
import { LoginPage } from "./pages/LoginPage";
import { PlanPage } from "./pages/PlanPage";
import { PortfolioPage } from "./pages/PortfolioPage";

// Telas novas: carregadas sob demanda para não pesar o bundle inicial.
const WatchlistPage = lazy(() =>
  import("./pages/WatchlistPage").then((m) => ({ default: m.WatchlistPage })),
);
const ReservePage = lazy(() =>
  import("./pages/ReservePage").then((m) => ({ default: m.ReservePage })),
);
// Carteira alvo é configuração estrutural: entra por link do Plantar, não vira aba.
const TargetPortfolioPage = lazy(() =>
  import("./pages/TargetPortfolioPage").then((m) => ({ default: m.TargetPortfolioPage })),
);

const TABS: { to: string; label: string }[] = [
  { to: "/plano", label: "Plantar" },
  { to: "/carteira", label: "Carteira" },
  { to: "/reserva", label: "Reserva" },
  { to: "/watchlist", label: "Descobrir" },
];

function PageFallback() {
  return (
    <main className="page">
      <p className="muted">Carregando…</p>
    </main>
  );
}

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
          <div className="header-actions">
            <ThemeToggle />
            <button className="header-action" onClick={() => logout.mutate()}>
              Sair
            </button>
          </div>
        </div>
      </header>

      <nav className="tabs" aria-label="Navegação principal">
        {TABS.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            className={({ isActive }) => `tab ${isActive ? "tab-on" : ""}`}
          >
            {t.label}
          </NavLink>
        ))}
      </nav>

      <Suspense fallback={<PageFallback />}>
        <Routes>
          <Route path="/plano" element={<PlanPage />} />
          <Route path="/carteira" element={<PortfolioPage />} />
          <Route path="/watchlist" element={<WatchlistPage />} />
          <Route path="/alvo" element={<TargetPortfolioPage />} />
          <Route path="/ativo/:ticker" element={<AssetPage />} />
          <Route path="/reserva" element={<ReservePage />} />
          <Route path="*" element={<Navigate to="/plano" replace />} />
        </Routes>
      </Suspense>

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
