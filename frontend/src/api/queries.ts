import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type {
  AccountIn,
  EntryIn,
  OrderIn,
  PlanRequest,
  Preferences,
  PreferencesBody,
  ProjectionRequest,
} from "../types";

export const keys = {
  health: ["health"] as const,
  auth: ["auth"] as const,
  glossary: ["glossary"] as const,
  strategies: ["strategies"] as const,
  portfolio: ["portfolio"] as const,
  preferences: ["preferences"] as const,
  watchlist: ["watchlist"] as const,
  income: ["income"] as const,
  incomeGoal: ["income-goal"] as const,
  incomeCalendar: ["income-calendar"] as const,
  incomeRealized: ["income-realized"] as const,
  incomeSnapshots: ["income-snapshots"] as const,
  incomeAnnounced: ["income-announced"] as const,
  fixedIncome: ["fixed-income"] as const,
  orders: ["orders"] as const,
  planLatest: ["plan-latest"] as const,
  planHistory: ["plan-history"] as const,
  watchlistRadar: ["watchlist-radar"] as const,
};

export const useHealth = () => useQuery({ queryKey: keys.health, queryFn: api.health });
export const useAuthStatus = () => useQuery({ queryKey: keys.auth, queryFn: api.authStatus });
// Nome distinto do hook de contexto `useGlossary` (hooks/useGlossary.ts).
export const useGlossaryQuery = () =>
  useQuery({ queryKey: keys.glossary, queryFn: api.glossary, staleTime: Infinity });
export const useStrategies = () =>
  useQuery({ queryKey: keys.strategies, queryFn: api.strategies, staleTime: Infinity });
export const usePortfolio = () => useQuery({ queryKey: keys.portfolio, queryFn: api.portfolio });
export const usePreferences = () =>
  useQuery({ queryKey: keys.preferences, queryFn: api.preferences });
export const useWatchlist = () => useQuery({ queryKey: keys.watchlist, queryFn: api.watchlist });

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (password: string) => api.login(password),
    onSuccess: () => qc.invalidateQueries(),
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.logout(),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.auth }),
  });
}

export function useSavePreferences() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: PreferencesBody) => api.savePreferences(body),
    onSuccess: (data) => qc.setQueryData(keys.preferences, data),
  });
}

export function useAddWatchlist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ ticker, note }: { ticker: string; note?: string }) =>
      api.addWatchlist(ticker, note),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.watchlist }),
  });
}

export function useRemoveWatchlist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ticker: string) => api.removeWatchlist(ticker),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.watchlist }),
  });
}

/** Favorito (⭐): tipos com favoritos têm o plano restrito a eles. */
export function useToggleFavorite() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ ticker, favorite }: { ticker: string; favorite: boolean }) =>
      api.setFavorite(ticker, favorite),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.watchlist }),
  });
}

/** Gerar plano é uma ação (POST com efeito), por isso é uma mutation, não query.
 *  O resultado alimenta o cache de 'último plano': navegar para outra aba e voltar
 *  NÃO perde mais o plano (nem força um novo POST de até 60s). */
export function usePlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: PlanRequest) => api.plan(req),
    onSuccess: (data) => {
      qc.setQueryData(keys.planLatest, data);
      qc.invalidateQueries({ queryKey: keys.planHistory });
    },
  });
}

/** Último plano persistido no servidor (restaura a PlanPage ao montar). */
export const usePlanLatest = () =>
  useQuery({
    queryKey: keys.planLatest,
    queryFn: api.planLatest,
    staleTime: Infinity, // só muda quando um novo plano é gerado (setQueryData acima)
    retry: false, // 404 = nunca gerou plano; não é erro a repetir
  });

export const usePlanHistory = () =>
  useQuery({ queryKey: keys.planHistory, queryFn: api.planHistory });

/** 'Próximo melhor aporte' — plano com a ESTRATÉGIA e parâmetros salvos do usuário
 *  (antes rodava 'equilibrado' hardcoded: um barsista via conselho de outra filosofia).
 *  Query cacheada: o POST /plan é caro (até 60s) e não deve rodar a cada mount. */
export function useNextBuy(prefs?: Preferences) {
  const req: PlanRequest | null = prefs
    ? {
        aporte: prefs.aporte_default && prefs.aporte_default > 0 ? prefs.aporte_default : 1000,
        strategy: prefs.strategy,
        targets: prefs.targets,
        max_assets: prefs.max_assets,
        max_weight_per_asset: prefs.max_weight_per_asset,
        min_ticket: prefs.min_ticket,
        allow_empty_portfolio: false,
        focus: prefs.focus, // mesmo foco da aba Plantar — conselho coerente entre abas
      }
    : null;
  return useQuery({
    queryKey: ["next-buy", req],
    queryFn: () => api.plan(req!),
    enabled: req != null,
    staleTime: 10 * 60 * 1000,
    retry: false,
  });
}

export const useIncome = () => useQuery({ queryKey: keys.income, queryFn: api.income });

export const useIncomeGoal = () =>
  useQuery({ queryKey: keys.incomeGoal, queryFn: api.incomeGoal });

export const useIncomeCalendar = () =>
  useQuery({ queryKey: keys.incomeCalendar, queryFn: api.incomeCalendar });

export const useIncomeRealized = () =>
  useQuery({ queryKey: keys.incomeRealized, queryFn: api.incomeRealized });

export const useIncomeSnapshots = () =>
  useQuery({ queryKey: keys.incomeSnapshots, queryFn: api.incomeSnapshots });

export const useIncomeAnnounced = () =>
  useQuery({ queryKey: keys.incomeAnnounced, queryFn: api.incomeAnnounced });

export const useYocHistory = (ticker: string) =>
  useQuery({
    queryKey: ["yoc-history", ticker],
    queryFn: () => api.yocHistory(ticker),
    enabled: !!ticker,
  });

export const useWatchlistRadar = () =>
  useQuery({
    queryKey: keys.watchlistRadar,
    queryFn: api.watchlistRadar,
    staleTime: 5 * 60 * 1000, // radar é caro (varre a watchlist inteira)
  });

// --- Renda fixa (rastreador / reserva) ---
export const useFixedIncome = () =>
  useQuery({ queryKey: keys.fixedIncome, queryFn: api.fixedIncome });

export function useCreateAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: AccountIn) => api.createAccount(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.fixedIncome }),
  });
}

export function useAddEntry() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: EntryIn }) => api.addEntry(id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.fixedIncome }),
  });
}

export const useEntries = (id: number) =>
  useQuery({
    queryKey: [...keys.fixedIncome, "entries", id],
    queryFn: () => api.listEntries(id),
    enabled: id > 0,
  });

export function useDeleteEntry() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ accountId, entryId }: { accountId: number; entryId: number }) =>
      api.deleteEntry(accountId, entryId),
    // invalida tudo sob ["fixed-income"] (resumo + listas de lançamentos)
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.fixedIncome }),
  });
}

export function useArchiveAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.archiveAccount(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.fixedIncome }),
  });
}

/** PATCH parcial da conta: renomear, trocar instituição/tipo e DESARQUIVAR. */
export function useUpdateAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: Parameters<typeof api.updateAccount>[1] }) =>
      api.updateAccount(id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.fixedIncome }),
  });
}

// --- Ordens ("já comprei") ---
export const useOrders = () => useQuery({ queryKey: keys.orders, queryFn: api.orders });

export function useCreateOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: OrderIn) => api.createOrder(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.orders }),
  });
}

export function useDeleteOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deleteOrder(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.orders }),
  });
}

export const useAsset = (ticker: string) =>
  useQuery({ queryKey: ["asset", ticker], queryFn: () => api.asset(ticker), enabled: !!ticker });

/** Projeção bola de neve: query cacheada pelos parâmetros (recalcula ao mudar os inputs). */
export const useProjection = (params: ProjectionRequest) =>
  useQuery({
    queryKey: ["projection", params],
    queryFn: () => api.projection(params),
    staleTime: Infinity,
  });
