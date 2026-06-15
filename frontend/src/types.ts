// Espelha os DTOs do backend (app/models).

export interface GlossaryEntry {
  label: string;
  definition: string;
  source: string;
  interpretation: string;
}
export type Glossary = Record<string, GlossaryEntry>;

export interface Metric {
  key: string;
  label: string;
  raw_value: number | null;
  display: string | null;
  normalized: number | null;
  weight: number;
  contribution: number | null;
  source: string;
  available: boolean;
  fallback_used: string | null;
  peer_group: string | null;
}

export interface SuggestedBuy {
  target_amount: number;
  price: number | null;
  shares: number;
  invested_exact: number;
  lot_size: number;
  lot_note: string | null;
}

export interface ScoredAsset {
  ticker: string;
  name: string | null;
  asset_class: string;
  sector: string | null;
  rank: number;
  composite_score: number;
  metrics: Metric[];
  data_completeness: string;
  suggested: SuggestedBuy | null;
  reasons: string[];
}

export interface PlanResponse {
  aporte: number;
  currency: string;
  as_of: string;
  weights: Record<string, number>;
  targets_by_class: Record<string, number>;
  current_by_class: Record<string, number>;
  ranking: ScoredAsset[];
  unallocated: number;
  warnings: string[];
  disclaimer: string;
}

export interface StrategyPreset {
  label: string;
  description: string;
  weights: Record<string, number>;
}
export interface StrategiesResponse {
  presets: Record<string, StrategyPreset>;
  default_targets: Record<string, number>;
}

export interface Position {
  ticker: string;
  name: string | null;
  asset_class: string;
  sector: string | null;
  value: number;
  weight: number;
  quantity: number | null;
  tags: string[];
  source: string;
}

export interface Portfolio {
  total_value: number;
  currency: string;
  positions: Position[];
  allocations: {
    by_class: Record<string, number>;
    by_sector: Record<string, number>;
  };
  as_of: string;
  source: string;
  warnings: string[];
}

export interface PlanRequest {
  aporte: number;
  strategy: string;
  max_assets?: number;
  max_weight_per_asset?: number;
  min_ticket?: number;
}
