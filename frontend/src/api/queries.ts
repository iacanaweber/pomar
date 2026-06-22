import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type { PlanRequest, PreferencesBody, ProjectionRequest } from "../types";

export const keys = {
  health: ["health"] as const,
  auth: ["auth"] as const,
  glossary: ["glossary"] as const,
  strategies: ["strategies"] as const,
  portfolio: ["portfolio"] as const,
  preferences: ["preferences"] as const,
  watchlist: ["watchlist"] as const,
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

/** Gerar plano é uma ação (POST com efeito), por isso é uma mutation, não query. */
export const usePlan = () => useMutation({ mutationFn: (req: PlanRequest) => api.plan(req) });

export const useIncome = () => useQuery({ queryKey: ["income"], queryFn: api.income });

/** Projeção bola de neve: query cacheada pelos parâmetros (recalcula ao mudar os inputs). */
export const useProjection = (params: ProjectionRequest) =>
  useQuery({
    queryKey: ["projection", params],
    queryFn: () => api.projection(params),
    staleTime: Infinity,
  });
