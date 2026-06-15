import { createContext, useContext } from "react";
import type { Glossary } from "../types";

export const GlossaryContext = createContext<Glossary>({});
export const useGlossary = () => useContext(GlossaryContext);
