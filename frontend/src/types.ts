// Tipos do contrato da API — fonte ÚNICA, derivada de /openapi.json.
// NÃO editar à mão os DTOs: regenerar o schema com `npm run gen:api` (precisa do
// backend acessível) e estes re-exports passam a refletir o contrato automaticamente.
import type { components } from "./api/schema";

type Schemas = components["schemas"];

// --- DTOs gerados do backend ---
export type PlanRequest = Schemas["PlanRequest"];
export type PlanResponse = Schemas["PlanResponse"];
export type PlanAsset = Schemas["PlanAsset"];
export type AssetAnalysis = Schemas["AssetAnalysis"];
export type SuggestedBuy = Schemas["SuggestedBuy"];
export type Portfolio = Schemas["Portfolio"];
export type Position = Schemas["Position"];
export type Allocations = Schemas["Allocations"];
export type ExposureResponse = Schemas["ExposureResponse"];
export type ExposureDimension = Schemas["ExposureDimension"];
export type ExposureItem = Schemas["ExposureItem"];
export type PreferencesBody = Schemas["PreferencesBody"];
export type WatchlistAdd = Schemas["WatchlistAdd"];
export type IncomeResponse = Schemas["IncomeResponse"];
export type IncomeAsset = Schemas["IncomeAsset"];
export type AssetDetailResponse = Schemas["AssetDetailResponse"];
export type Asset = Schemas["Asset"];
export type Fundamentals = Schemas["Fundamentals"];
export type ReserveSuggestion = Schemas["ReserveSuggestion"];
export type FixedIncomeSuggestion = Schemas["FixedIncomeSuggestion"];
export type IndexerAllocation = Schemas["IndexerAllocation"];
export type LegacySummary = Schemas["LegacySummary"];

// --- Yield on Cost (dos snapshots mensais) ---
export type YocPoint = Schemas["YocPoint"];

// --- curva de rendimento (TWR semanal) ---
export type PerformanceResponse = Schemas["PerformanceResponse"];
export type WeeklyPoint = Schemas["WeeklyPoint"];
export type BenchmarkSeries = Schemas["BenchmarkSeries"];

// --- Planos salvos e radar da watchlist (v4) ---
export type PlanSummary = Schemas["PlanSummary"];
export type RadarResponse = Schemas["RadarResponse"];
export type RadarItem = Schemas["RadarItem"];

// --- Renda fixa (rastreador) ---
export type FixedIncomeSummary = Schemas["FixedIncomeSummary"];
export type FloorStatus = Schemas["FloorStatus"];
export type AccountSummary = Schemas["AccountSummary"];
export type AccountIn = Schemas["AccountIn"];
export type AccountPatch = Schemas["AccountPatch"];
export type EntryIn = Schemas["EntryIn"];
// Literals são inlinados pelo OpenAPI (não viram schema próprio): derivam do DTO.
export type Purpose = AccountSummary["purpose"];
export type Liquidity = AccountSummary["liquidity"];
export type NewLiquidity = AccountIn["liquidity"];

// --- Cesta de RENDA_FIXA: os itens são tags de indexador, não tickers ---
export type IndexersResponse = Schemas["IndexersResponse"];
export type IndexerSlice = Schemas["IndexerSlice"];

// --- Rótulos por dimensão (bucket / indexer / geography) ---
export type LabelOut = Schemas["LabelOut"];
export type LabelIn = Schemas["LabelIn"];
export type AssignmentOut = Schemas["AssignmentOut"];
export type AssignmentsIn = Schemas["AssignmentsIn"];
export type LabelDimension = "bucket" | "indexer" | "geography";

/** Lançamento de renda fixa (a rota GET .../entries devolve { items: FixedIncomeEntry[] }). */
export interface FixedIncomeEntry {
  id: number;
  account_id: number;
  kind: "balance" | "deposit" | "withdrawal";
  amount: number;
  entry_date: string;
  note?: string | null;
}

// --- Ordens ("já comprei") ---
export type OrderIn = Schemas["OrderIn"];
export type OrderOut = Schemas["OrderOut"];
export type OrdersListResponse = Schemas["OrdersListResponse"];

// --- Tipos de respostas que o FastAPI devolve como dict livre (sem response_model),
//     portanto não vêm tipados no OpenAPI; declarados aqui manualmente. ---
export interface GlossaryEntry {
  label: string;
  definition: string;
  source: string;
  interpretation: string;
}
export type Glossary = Record<string, GlossaryEntry>;

export interface Preferences {
  aporte_default: number | null;
  targets: Record<string, number>;
  min_ticket: number;
  lot_mode: string;
  /** @deprecated Virou o peso da classe RENDA_FIXA + o piso em R$. Não é mais lido. */
  reserve_target: number;
  bazin_target_mode: string;
  bazin_target_yield?: number | null;
  /** Carteira alvo: peso (0..1) de cada item dentro da sua classe. Em RENDA_FIXA o item
   *  é uma tag de indexador (CDI, IPCA…); nas demais, um ticker. */
  class_targets: Record<string, Record<string, number>>;
  /** Piso da reserva: o mínimo que fica em renda fixa de resgate imediato. */
  reserve_floor_amount: number;
  reserve_floor_date: string | null;
  reserve_floor_index: "none" | "ipca";
  /** Se os ativos fora da carteira alvo entram na base dos alvos em R$ das demais classes. */
  legacy_in_total: boolean;
  /** Teto do aporte para o PISO da reserva (0..1). 1 = prioridade absoluta. */
  reserve_floor_share: number;
}

export interface WatchlistItem {
  ticker: string;
  asset_class: string;
  note: string | null;
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
