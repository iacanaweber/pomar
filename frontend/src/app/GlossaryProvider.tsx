import type { ReactNode } from "react";
import { GlossaryContext } from "../hooks/useGlossary";
import { useGlossaryQuery } from "../api/queries";

/** Carrega o glossário (react-query) e o disponibiliza via contexto para os tooltips. */
export function GlossaryProvider({ children }: { children: ReactNode }) {
  const { data } = useGlossaryQuery();
  return <GlossaryContext.Provider value={data ?? {}}>{children}</GlossaryContext.Provider>;
}
