import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type {
  AccountIn,
  EntryIn,
  OrderIn,
  PlanRequest,
  PreferencesBody,
} from "../types";

export const keys = {
  health: ["health"] as const,
  auth: ["auth"] as const,
  glossary: ["glossary"] as const,
  portfolio: ["portfolio"] as const,
  preferences: ["preferences"] as const,
  watchlist: ["watchlist"] as const,
  income: ["income"] as const,
  incomeRealized: ["income-realized"] as const,
  fixedIncome: ["fixed-income"] as const,
  orders: ["orders"] as const,
  planLatest: ["plan-latest"] as const,
  watchlistRadar: ["watchlist-radar"] as const,
};

export const useHealth = () => useQuery({ queryKey: keys.health, queryFn: api.health });
export const useAuthStatus = () => useQuery({ queryKey: keys.auth, queryFn: api.authStatus });
// Nome distinto do hook de contexto `useGlossary` (hooks/useGlossary.ts).
export const useGlossaryQuery = () =>
  useQuery({ queryKey: keys.glossary, queryFn: api.glossary, staleTime: Infinity });
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

/** Gerar plano é uma ação (POST com efeito), por isso é uma mutation, não query.
 *  O resultado alimenta o cache de 'último plano': navegar para outra aba e voltar
 *  NÃO perde mais o plano (nem força um novo POST de até 60s). */
export function usePlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: PlanRequest) => api.plan(req),
    onSuccess: (data) => qc.setQueryData(keys.planLatest, data),
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

export const useIncome = () => useQuery({ queryKey: keys.income, queryFn: api.income });

export const useIncomeRealized = () =>
  useQuery({ queryKey: keys.incomeRealized, queryFn: api.incomeRealized });

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
