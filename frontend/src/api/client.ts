import type {
  AccountIn,
  AccountSummary,
  AssetDetailResponse,
  AuthStatus,
  CalendarResponse,
  EntryIn,
  FixedIncomeEntry,
  FixedIncomeSummary,
  Glossary,
  HealthStatus,
  IncomeGoalResponse,
  IncomeResponse,
  OrderIn,
  OrderOut,
  OrdersListResponse,
  PlanRequest,
  PlanResponse,
  Portfolio,
  Preferences,
  PreferencesBody,
  ProjectionRequest,
  ProjectionResponse,
  StrategiesResponse,
  WatchlistItem,
} from "../types";

/** Erro de API com mensagem amigável já traduzida para o usuário. */
export class ApiError extends Error {
  status: number;
  userMessage: string;
  raw: unknown;
  constructor(status: number, userMessage: string, raw?: unknown) {
    super(userMessage);
    this.name = "ApiError";
    this.status = status;
    this.userMessage = userMessage;
    this.raw = raw;
  }
}

function translate(status: number, path: string, detail?: string): string {
  if (status === 401) return "Sessão necessária. Entre com sua senha.";
  if (status === 503) return "Servidor sem senha configurada (APP_PASSWORD).";
  if ([502, 504].includes(status)) {
    if (path.includes("/portfolio")) {
      return "Não consegui falar com o Ghostfolio. Verifique a conexão em Ajustes.";
    }
    return "Uma fonte de dados externa está indisponível. Tente de novo em instantes.";
  }
  return detail || `Erro ${status} ao acessar ${path}`;
}

async function request<T>(path: string, opts: RequestInit = {}, timeoutMs = 15000): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let res: Response;
  try {
    res = await fetch(path, {
      credentials: "include", // cookie de sessão HttpOnly
      signal: controller.signal,
      ...opts,
    });
  } catch (err) {
    clearTimeout(timer);
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError(0, "A operação demorou demais (a brapi grátis costuma ser lenta). Tente de novo.");
    }
    throw new ApiError(0, "Falha de rede ao acessar o servidor.");
  }
  clearTimeout(timer);
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new ApiError(res.status, translate(res.status, path, body.detail), body);
  }
  return (await res.json()) as T;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  // auth / meta
  health: () => request<HealthStatus>("/api/health"),
  authStatus: () => request<AuthStatus>("/api/auth/status"),
  login: (password: string) => request<{ ok: boolean }>("/api/login", json({ password })),
  logout: () => request<{ ok: boolean }>("/api/logout", { method: "POST" }),
  glossary: () => request<Glossary>("/api/glossary"),
  strategies: () => request<StrategiesResponse>("/api/strategies"),

  // carteira / mercado
  portfolio: () => request<Portfolio>("/api/portfolio"),
  asset: (ticker: string) => request<AssetDetailResponse>(`/api/asset/${ticker}`, {}, 30000),

  // preferências / watchlist
  preferences: () => request<Preferences>("/api/preferences"),
  savePreferences: (body: PreferencesBody) =>
    request<Preferences>("/api/preferences", { ...json(body), method: "PUT" }),
  watchlist: () => request<{ items: WatchlistItem[] }>("/api/watchlist"),
  addWatchlist: (ticker: string, note?: string) =>
    request<{ ticker: string; asset_class: string }>("/api/watchlist", json({ ticker, note })),
  removeWatchlist: (ticker: string) =>
    request<{ ok: boolean }>(`/api/watchlist/${ticker}`, { method: "DELETE" }),

  // renda passiva
  income: () => request<IncomeResponse>("/api/income", {}, 60000),
  projection: (body: ProjectionRequest) =>
    request<ProjectionResponse>("/api/income/projection", json(body)),
  incomeGoal: () => request<IncomeGoalResponse>("/api/income/goal", {}, 60000),
  incomeCalendar: () => request<CalendarResponse>("/api/income/calendar", {}, 60000),

  // renda fixa (rastreador / reserva)
  fixedIncome: () => request<FixedIncomeSummary>("/api/fixed-income/summary"),
  createAccount: (body: AccountIn) =>
    request<AccountSummary>("/api/fixed-income/accounts", json(body)),
  updateAccount: (id: number, body: Partial<AccountIn> & { archived?: boolean }) =>
    request<AccountSummary>(`/api/fixed-income/accounts/${id}`, { ...json(body), method: "PATCH" }),
  archiveAccount: (id: number) =>
    request<{ ok: boolean }>(`/api/fixed-income/accounts/${id}`, { method: "DELETE" }),
  addEntry: (id: number, body: EntryIn) =>
    request<AccountSummary>(`/api/fixed-income/accounts/${id}/entries`, json(body)),
  listEntries: (id: number) =>
    request<{ items: FixedIncomeEntry[] }>(`/api/fixed-income/accounts/${id}/entries`),
  deleteEntry: (accountId: number, entryId: number) =>
    request<{ ok: boolean }>(
      `/api/fixed-income/accounts/${accountId}/entries/${entryId}`,
      { method: "DELETE" },
    ),

  // ordens ("já comprei")
  orders: () => request<OrdersListResponse>("/api/orders"),
  createOrder: (body: OrderIn) => request<OrderOut>("/api/orders", json(body)),
  deleteOrder: (id: number) =>
    request<{ ok: boolean }>(`/api/orders/${id}`, { method: "DELETE" }),

  // plano (mais lento -> timeout maior)
  plan: (req: PlanRequest) => request<PlanResponse>("/api/plan", json(req), 60000),
};
