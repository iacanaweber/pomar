import { useSyncExternalStore } from "react";
import { getPwaStatus, subscribePwa, type PwaStatus } from "../lib/pwa";

/** Estado do service worker como store externa: ele é atualizado por eventos do
 *  navegador (`updatefound`, `statechange`), não por render do React. */
export const usePwa = (): PwaStatus =>
  useSyncExternalStore(subscribePwa, getPwaStatus, getPwaStatus);
