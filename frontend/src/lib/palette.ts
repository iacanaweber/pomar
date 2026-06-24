// Paleta compartilhada dos gráficos. Extraída de PortfolioPage (estava hardcoded e
// duplicável). Usada pelo donut de carteira e pelo perfil BESST.

/** Paleta genérica com tons de verde/terra + acentos, suficiente para muitas fatias. */
export const PALETTE = [
  "#2e7d32", "#66bb6a", "#f9a825", "#1b5e20", "#9ccc65", "#ef6c00",
  "#26a69a", "#8d6e63", "#5c6bc0", "#ec407a", "#789262", "#ffb300",
  "#00897b", "#c0ca33", "#6d4c41", "#42a5f5",
];

/**
 * Classificação BESST (Bancos, Energia, Seguros, Saneamento, Telecom = perenes/defensivos).
 * Mapeia um setor livre para uma das categorias do método. Tudo que não for essencial
 * cai em "Cíclico"; sem setor → "Sem classificação".
 */
export type BesstCategory =
  | "Bancos"
  | "Energia"
  | "Seguros"
  | "Saneamento"
  | "Telecom"
  | "Cíclico"
  | "Sem classificação";

/** Cores semânticas: essenciais em verdes, cíclico em âmbar/terra, sem dado em cinza. */
export const BESST_COLORS: Record<BesstCategory, string> = {
  Bancos: "#1b5e20",
  Energia: "#2e7d32",
  Seguros: "#388e3c",
  Saneamento: "#43a047",
  Telecom: "#66bb6a",
  Cíclico: "#f9a825",
  "Sem classificação": "#9e9e9e",
};

/** Categorias consideradas "essenciais/defensivas" para o cálculo de % defensivo. */
export const BESST_DEFENSIVE: BesstCategory[] = [
  "Bancos",
  "Energia",
  "Seguros",
  "Saneamento",
  "Telecom",
];

const SECTOR_PATTERNS: { test: RegExp; category: BesstCategory }[] = [
  { test: /banc|financ|crédito|credito/i, category: "Bancos" },
  { test: /energ|elétr|eletr|utilit|geração|geracao|transmiss/i, category: "Energia" },
  { test: /segur|previd|capitaliz/i, category: "Seguros" },
  { test: /saneam|água|agua|esgoto/i, category: "Saneamento" },
  { test: /telecom|telefon|comunic/i, category: "Telecom" },
];

/** Resolve um setor livre para a categoria BESST mais próxima. */
export function besstCategory(sector?: string | null): BesstCategory {
  if (!sector || !sector.trim()) return "Sem classificação";
  for (const { test, category } of SECTOR_PATTERNS) {
    if (test.test(sector)) return category;
  }
  return "Cíclico";
}
