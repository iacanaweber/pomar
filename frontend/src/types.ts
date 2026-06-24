// Tipos do contrato da API — fonte ÚNICA, derivada de /openapi.json.
// NÃO editar à mão os DTOs: regenerar o schema com `npm run gen:api` (precisa do
// backend acessível) e estes re-exports passam a refletir o contrato automaticamente.
import type { components } from "./api/schema";

type Schemas = components["schemas"];

// --- DTOs gerados do backend ---
export type PlanRequest = Schemas["PlanRequest"];
export type PlanResponse = Schemas["PlanResponse"];
export type ScoredAsset = Schemas["ScoredAsset"];
export type Metric = Schemas["Metric"];
export type SuggestedBuy = Schemas["SuggestedBuy"];
export type Portfolio = Schemas["Portfolio"];
export type Position = Schemas["Position"];
export type Allocations = Schemas["Allocations"];
export type PreferencesBody = Schemas["PreferencesBody"];
export type WatchlistAdd = Schemas["WatchlistAdd"];
export type IncomeResponse = Schemas["IncomeResponse"];
export type IncomeAsset = Schemas["IncomeAsset"];
export type ProjectionRequest = Schemas["ProjectionRequest"];
export type ProjectionResponse = Schemas["ProjectionResponse"];
export type ProjectionPoint = Schemas["ProjectionPoint"];
export type AssetDetailResponse = Schemas["AssetDetailResponse"];
export type Asset = Schemas["Asset"];
export type Fundamentals = Schemas["Fundamentals"];
export type ReserveSuggestion = Schemas["ReserveSuggestion"];

// --- Objetivo de renda + calendário ---
export type IncomeGoalResponse = Schemas["IncomeGoalResponse"];
export type CalendarResponse = Schemas["CalendarResponse"];
export type CalendarMonth = Schemas["CalendarMonth"];

// --- Renda fixa (rastreador) ---
export type FixedIncomeSummary = Schemas["FixedIncomeSummary"];
export type AccountSummary = Schemas["AccountSummary"];
export type AccountIn = Schemas["AccountIn"];
export type EntryIn = Schemas["EntryIn"];

// --- Ordens ("já comprei") ---
export type OrderIn = Schemas["OrderIn"];
export type OrderOut = Schemas["OrderOut"];
export type OrdersListResponse = Schemas["OrdersListResponse"];

/** Item de proventos por ativo dentro de um mês do calendário (dict livre no backend). */
export interface CalendarByAsset {
  ticker: string;
  income: number;
}

// --- Tipos de respostas que o FastAPI devolve como dict livre (sem response_model),
//     portanto não vêm tipados no OpenAPI; declarados aqui manualmente. ---
export interface GlossaryEntry {
  label: string;
  definition: string;
  source: string;
  interpretation: string;
}
export type Glossary = Record<string, GlossaryEntry>;

export interface StrategyPreset {
  label: string;
  description: string;
  weights: Record<string, number>;
}
export interface StrategiesResponse {
  presets: Record<string, StrategyPreset>;
  default_targets: Record<string, number>;
}

export interface Preferences {
  strategy: string;
  aporte_default: number | null;
  targets: Record<string, number>;
  weights: Record<string, number>;
  max_assets: number;
  max_weight_per_asset: number;
  min_ticket: number;
  lot_mode: string;
  reserve_target: number;
  bazin_target_mode: string;
  bazin_target_yield?: number | null;
  target_monthly_income?: number | null;
  target_horizon_years?: number | null;
  annual_growth?: number | null;
}

export interface WatchlistItem {
  ticker: string;
  asset_class: string;
  note: string | null;
  favorite: number;
  added_at: string | null;
  last_validated_at: string | null;
  valid: number;
}

export interface HealthStatus {
  status?: string;
  ghostfolio: boolean;
  brapi: boolean;
}

export interface AuthStatus {
  auth_required: boolean;
  authenticated: boolean;
}
