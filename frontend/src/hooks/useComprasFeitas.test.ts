import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";

import { useComprasFeitas } from "./useComprasFeitas";

beforeEach(() => localStorage.clear());
afterEach(() => vi.restoreAllMocks());

describe("useComprasFeitas", () => {
  it("marca e desmarca", () => {
    const { result } = renderHook(() => useComprasFeitas(42));
    expect(result.current.feito("IVVB11")).toBe(false);

    act(() => result.current.alternar("IVVB11"));
    expect(result.current.feito("IVVB11")).toBe(true);
    expect(result.current.quantidade).toBe(1);

    act(() => result.current.alternar("IVVB11"));
    expect(result.current.feito("IVVB11")).toBe(false);
    expect(result.current.quantidade).toBe(0);
  });

  it("o ticker casa independentemente de caixa", () => {
    const { result } = renderHook(() => useComprasFeitas(42));
    act(() => result.current.alternar("ivvb11"));
    expect(result.current.feito("IVVB11")).toBe(true);
  });

  it("sobrevive a recarregar a página", () => {
    const primeiro = renderHook(() => useComprasFeitas(42));
    act(() => primeiro.result.current.alternar("IVVB11"));
    primeiro.unmount();

    const segundo = renderHook(() => useComprasFeitas(42));
    expect(segundo.result.current.feito("IVVB11")).toBe(true);
  });

  it("plano novo começa com a lista limpa", () => {
    const antigo = renderHook(() => useComprasFeitas(42));
    act(() => antigo.result.current.alternar("IVVB11"));

    const novo = renderHook(() => useComprasFeitas(43));
    expect(novo.result.current.feito("IVVB11")).toBe(false);
  });

  it("gravar apaga as chaves de outros planos — o armazenamento não cresce sem limite", () => {
    const antigo = renderHook(() => useComprasFeitas(42));
    act(() => antigo.result.current.alternar("IVVB11"));
    expect(localStorage.getItem("pomar:comprei:42")).not.toBeNull();

    const novo = renderHook(() => useComprasFeitas(43));
    act(() => novo.result.current.alternar("BOVA11"));

    expect(localStorage.getItem("pomar:comprei:42")).toBeNull();
    expect(localStorage.getItem("pomar:comprei:43")).not.toBeNull();
  });

  it("sem plano persistido, o tique vale na sessão mas não é gravado", () => {
    // Um plano pode não ter id (não foi salvo). O checklist ainda tem de funcionar: um
    // checkbox que não faz nada ao ser clicado é pior do que não persistir.
    const { result } = renderHook(() => useComprasFeitas(null));
    act(() => result.current.alternar("IVVB11"));
    expect(result.current.feito("IVVB11")).toBe(true);
    expect(localStorage.length).toBe(0);
  });

  // O modo de falha que a guarda existe para evitar: a leitura acontece num
  // inicializador de `useState`, e sem try/catch derruba a página no ErrorBoundary.
  it("armazenamento que lança na LEITURA não derruba o componente", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("negado", "SecurityError");
    });
    const { result } = renderHook(() => useComprasFeitas(42));
    expect(result.current.feito("IVVB11")).toBe(false);
  });

  it("armazenamento que lança na ESCRITA mantém o tique na sessão", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("cota", "QuotaExceededError");
    });
    const { result } = renderHook(() => useComprasFeitas(42));
    act(() => result.current.alternar("IVVB11"));
    // não persistiu, mas a sessão continua utilizável
    expect(result.current.feito("IVVB11")).toBe(true);
  });

  it("conteúdo corrompido no armazenamento é ignorado", () => {
    localStorage.setItem("pomar:comprei:42", "{isto não é json");
    const { result } = renderHook(() => useComprasFeitas(42));
    expect(result.current.quantidade).toBe(0);
  });
});
