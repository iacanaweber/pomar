import type {
  AccountIn,
  AccountPatch,
  AccountSummary,
  AssetDetailResponse,
  AssignmentOut,
  AssignmentsIn,
  AuthStatus,
  EntryIn,
  ExposureResponse,
  FixedIncomeEntry,
  FixedIncomeSummary,
  Glossary,
  HealthStatus,
  IncomeResponse,
  IndexersResponse,
  LabelDimension,
  LabelOut,
  OrderIn,
  OrderOut,
  OrdersListResponse,
  PerformanceResponse,
  PlanRequest,
  PlanResponse,
  Portfolio,
  Preferences,
  PreferencesBody,
  RadarResponse,
  WatchlistItem,
  YocPoint,
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
  if (status === 401) return "Sessão expirada.";
  // 503 com detail é mensagem específica do backend (ex.: plano abortado sem carteira)
  if (status === 503) return detail || "Servidor sem senha configurada (APP_PASSWORD).";
  if ([502, 504].includes(status)) {
    if (path.includes("/portfolio")) {
      return "Ghostfolio inacessível. Verifique o container e o GHOSTFOLIO_URL.";
    }
    return "Fonte externa indisponível.";
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
      throw new ApiError(0, "Tempo esgotado (a brapi grátis é lenta).");
    }
    throw new ApiError(0, "Sem resposta do servidor.");
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

  // carteira / mercado
  portfolio: () => request<Portfolio>("/api/portfolio"),
  // composição do patrimônio INTEIRO (renda variável + renda fixa marcada), por dimensão
  exposure: () => request<ExposureResponse>("/api/portfolio/exposure", {}, 30000),
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
  yocHistory: (ticker: string) => request<YocPoint[]>(`/api/income/yoc/${ticker}`),

  // renda fixa (rastreador / reserva) — lista TUDO; a UI separa ativas de arquivadas
  fixedIncome: () => request<FixedIncomeSummary>("/api/fixed-income/summary?include_archived=true"),
  createAccount: (body: AccountIn) =>
    request<AccountSummary>("/api/fixed-income/accounts", json(body)),
  updateAccount: (id: number, body: AccountPatch) =>
    request<AccountSummary>(`/api/fixed-income/accounts/${id}`, { ...json(body), method: "PATCH" }),
  archiveAccount: (id: number) =>
    request<{ ok: boolean }>(`/api/fixed-income/accounts/${id}`, { method: "DELETE" }),
  addEntry: (id: number, body: EntryIn) =>
    request<AccountSummary>(`/api/fixed-income/accounts/${id}/entries`, json(body)),
  listEntries: (id: number) =>
    request<{ items: FixedIncomeEntry[] }>(`/api/fixed-income/accounts/${id}/entries`),
  deleteEntry: (accountId: number, entryId: number) =>
    request<{ ok: boolean }>(`/api/fixed-income/accounts/${accountId}/entries/${entryId}`, {
      method: "DELETE",
    }),

  // composição da classe RENDA_FIXA por tag de indexador (atual × alvo)
  indexers: () => request<IndexersResponse>("/api/fixed-income/indexers", {}, 30000),

  // rótulos por dimensão (bucket dirige a compra; indexer e geography descrevem)
  labels: (dimension?: LabelDimension) =>
    request<LabelOut[]>(`/api/labels${dimension ? `?dimension=${dimension}` : ""}`),
  assignments: (params: {
    dimension?: LabelDimension;
    subjectType?: "ticker" | "fi_account";
    subjectId?: string;
    subjects?: string[];
    includeDefaults?: boolean;
  }) => {
    const q = new URLSearchParams();
    if (params.dimension) q.set("dimension", params.dimension);
    if (params.subjectType) q.set("subject_type", params.subjectType);
    if (params.subjectId) q.set("subject_id", params.subjectId);
    if (params.subjects?.length) q.set("subjects", params.subjects.join(","));
    if (params.includeDefaults) q.set("include_defaults", "true");
    return request<AssignmentOut[]>(`/api/labels/assignments?${q.toString()}`);
  },
  setAssignments: (body: AssignmentsIn) =>
    request<AssignmentOut[]>("/api/labels/assignments", { ...json(body), method: "PUT" }),

  // ordens ("já comprei")
  orders: () => request<OrdersListResponse>("/api/orders"),
  createOrder: (body: OrderIn) => request<OrderOut>("/api/orders", json(body)),
  deleteOrder: (id: number) => request<{ ok: boolean }>(`/api/orders/${id}`, { method: "DELETE" }),

  // plano (mais lento -> timeout maior)
  plan: (req: PlanRequest) => request<PlanResponse>("/api/plan", json(req), 60000),
  planLatest: () => request<PlanResponse>("/api/plan/latest"),

  // curva de rendimento (TWR semanal contra os índices)
  performance: (window = "all") =>
    request<PerformanceResponse>(`/api/performance?window=${window}`, {}, 30000),

  // radar da watchlist (preço-teto de todos os observados)
  watchlistRadar: () => request<RadarResponse>("/api/watchlist/radar", {}, 60000),
};
