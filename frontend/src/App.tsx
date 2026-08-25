import { Suspense, lazy } from "react";
import { Navigate, NavLink, Route, Routes } from "react-router-dom";
import { useAuthStatus, useLogout } from "./api/queries";
import { GlossaryProvider } from "./app/GlossaryProvider";
import { BrandMark, Icon, type IconName } from "./components/Icon";
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

// O ícone só aparece na barra inferior do celular, onde o rótulo sozinho fica apertado
// em 360px. No desktop ele some e o texto continua sendo a âncora.
const TABS: { to: string; label: string; icon: IconName }[] = [
  { to: "/plano", label: "Plantar", icon: "plant" },
  { to: "/carteira", label: "Carteira", icon: "basket" },
  { to: "/reserva", label: "Reserva", icon: "vault" },
  { to: "/watchlist", label: "Descobrir", icon: "search" },
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
          <BrandMark size={26} />
          <h1>Pomar</h1>
          <div className="header-actions">
            <ThemeToggle />
          </div>
        </div>
      </header>

      {/* No celular esta barra é fixada no rodapé (ver .tabs em index.css): em standalone
          o topo da tela fica longe do polegar, e trocar de aba é o gesto mais repetido do
          app. No desktop ela continua onde sempre esteve. */}
      <nav className="tabs" aria-label="Navegação principal">
        {TABS.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            className={({ isActive }) => `tab ${isActive ? "tab-on" : ""}`}
          >
            <span className="tab-icon">
              <Icon name={t.icon} size={20} />
            </span>
            <span className="tab-label">{t.label}</span>
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
        <button className="link-button footer-exit" onClick={() => logout.mutate()}>
          Sair
        </button>
        <span>Fundamentus · StatusInvest · brapi · Ghostfolio</span>
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
