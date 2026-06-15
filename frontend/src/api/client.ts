import type { Glossary, PlanRequest, PlanResponse, StrategiesResponse } from "../types";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${res.status} em ${path}`);
  return res.json();
}

export const api = {
  glossary: () => get<Glossary>("/api/glossary"),
  strategies: () => get<StrategiesResponse>("/api/strategies"),
  health: () => get<{ ghostfolio: boolean; brapi: boolean }>("/api/health"),
  plan: async (req: PlanRequest): Promise<PlanResponse> => {
    const res = await fetch("/api/plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || `Erro ${res.status} ao gerar o plano`);
    }
    return res.json();
  },
};
