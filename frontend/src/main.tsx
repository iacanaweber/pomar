import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { ErrorBoundary } from "./app/ErrorBoundary";
import { queryClient } from "./app/queryClient";
import { registerServiceWorker } from "./lib/pwa";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  </React.StrictMode>,
);

// Service worker: só em produção e em contexto seguro; /api/ nunca passa por ele (ver
// public/sw.js). O estado fica visível nos Ajustes — falha silenciosa aqui vira "o app
// não abre sem internet" descoberto meses depois.
registerServiceWorker();
