import { useState } from "react";
import { ApiError } from "../api/client";
import { useLogin } from "../api/queries";

export function LoginPage() {
  const [password, setPassword] = useState("");
  const login = useLogin();

  return (
    <main className="page login-page">
      <div className="login-card">
        <div className="brand">
          <span className="logo">🌳</span>
          <div>
            <h1>Pomar</h1>
            <p className="muted">Plante seus aportes, colha dividendos.</p>
          </div>
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (password) login.mutate(password);
          }}
        >
          <label className="field">
            <span>Senha</span>
            <input
              type="password"
              autoComplete="current-password"
              autoFocus
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Sua senha"
            />
          </label>
          {login.isError && (
            <div className="banner banner-error">
              {login.error instanceof ApiError ? login.error.userMessage : "Falha ao entrar."}
            </div>
          )}
          <button className="primary" type="submit" disabled={login.isPending || !password}>
            {login.isPending ? "Entrando…" : "Entrar"}
          </button>
        </form>
      </div>
    </main>
  );
}
