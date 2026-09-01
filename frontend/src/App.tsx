import { Suspense, lazy } from "react";
import { Navigate, NavLink, Route, Routes } from "react-router-dom";
import { ApiError } from "./api/client";
import { useAuthStatus, useLogout } from "./api/queries";
import { GlossaryProvider } from "./app/GlossaryProvider";
import { BrandMark, Icon, type IconName } from "./components/Icon";
import { ThemeToggle } from "./components/ThemeToggle";
import { LoginPage } from "./pages/LoginPage";
import { PlanPage } from "./pages/PlanPage";
import { PortfolioPage } from "./pages/PortfolioPage";

// Carregadas sob demanda. O critério é FREQUÊNCIA, não idade da tela: o que se abre em
// toda sessão vem no bundle inicial; folha de detalhe e telas de configuração, não.
// Estava invertido — AssetPage, que é folha, vinha eager, e a watchlist, que era aba de
// topo, vinha lazy.
const AssetPage = lazy(() => import("./pages/AssetPage").then((m) => ({ default: m.AssetPage })));
const WatchlistPage = lazy(() =>
  import("./pages/WatchlistPage").then((m) => ({ default: m.WatchlistPage })),
);
const ReservePage = lazy(() =>
  import("./pages/reserve/ReservePage").then((m) => ({ default: m.ReservePage })),
);
const TargetPortfolioPage = lazy(() =>
  import("./pages/TargetPortfolioPage").then((m) => ({ default: m.TargetPortfolioPage })),
);

// O ícone só aparece na barra inferior do celular, onde o rótulo sozinho fica apertado
// em 360px. No desktop ele some e o texto continua sendo a âncora.
// "Descobrir" saiu da barra: ela existia para achar ação pagadora abaixo do preço-teto
// de Bazin, pergunta que a estratégia atual (acumulação em ETF) não faz mais. Segue
// existindo em /watchlist, alcançável por link, até virar outra coisa. No lugar dela
// entrou /alvo, que DEFINE tudo o que o Plantar calcula e só era acessível por link de
// dentro das páginas — a tela mais estrutural do app era a única sem porta.
const TABS: { to: string; label: string; icon: IconName }[] = [
  { to: "/plano", label: "Plantar", icon: "plant" },
  { to: "/carteira", label: "Carteira", icon: "basket" },
  { to: "/alvo", label: "Alvo", icon: "target" },
  { to: "/reserva", label: "Reserva", icon: "vault" },
];

function PageFallback() {
  return (
    <main className="page">
      <p className="muted">Carregando</p>
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
          {/* Marca do app, não título da página: um <h1> aqui fica em TODA tela e rouba o
              nível de quem deveria tê-lo. O h1 de cada página é o nome da própria tela. */}
          <span className="brand-name">Pomar</span>
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
        <p className="muted" role="status">
          Carregando…
        </p>
      </main>
    );
  }
  // Sem resposta do backend não se sabe se há sessão. Renderizar o app inteiro nesse
  // caso era afirmar que sim: cada aba abria e falhava por conta própria, com cinco
  // mensagens de erro diferentes para uma causa só.
  if (auth.isError || !auth.data) {
    return (
      <main className="page">
        <div className="banner banner-error" role="alert">
          <Icon name="alert" size={15} />{" "}
          {auth.error instanceof ApiError
            ? auth.error.userMessage
            : "Não foi possível falar com o servidor."}
        </div>
        <p className="link-row">
          <button className="link-button" onClick={() => auth.refetch()}>
            Tentar de novo
          </button>
        </p>
      </main>
    );
  }
  if (auth.data.auth_required && !auth.data.authenticated) {
    return <LoginPage />;
  }
  return (
    <GlossaryProvider>
      <AppShell />
    </GlossaryProvider>
  );
}
