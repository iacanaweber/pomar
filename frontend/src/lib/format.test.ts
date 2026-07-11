import { describe, expect, it } from "vitest";
import { brToISO, isoToBR, parseBRL } from "./format";

describe("parseBRL — a função que lê dinheiro digitado", () => {
  it("entende pt-BR com vírgula decimal", () => {
    expect(parseBRL("1.234,56")).toBe(1234.56);
    expect(parseBRL("1500,00")).toBe(1500);
    expect(parseBRL("0,5")).toBe(0.5);
  });

  it("NÃO transforma ponto decimal em milhar (bug do aporte ×100)", () => {
    // "1500.00" virava 150.000 — um aporte gerava plano para cem vezes o valor
    expect(parseBRL("1500.00")).toBe(1500);
    expect(parseBRL("99.9")).toBe(99.9);
    expect(parseBRL("2000.5")).toBe(2000.5);
  });

  it("mantém o ponto como milhar quando é milhar", () => {
    expect(parseBRL("1.500")).toBe(1500); // 3 dígitos após o ponto = milhar
    expect(parseBRL("1.234.567")).toBe(1234567);
  });

  it("inteiros e lixo", () => {
    expect(parseBRL("2000")).toBe(2000);
    expect(parseBRL(" 350 ")).toBe(350);
    expect(Number.isNaN(parseBRL(""))).toBe(true);
    expect(Number.isNaN(parseBRL("abc"))).toBe(true);
  });
});

describe("datas brasileiras", () => {
  it("brToISO valida calendário de verdade", () => {
    expect(brToISO("02/01/2026")).toBe("2026-01-02");
    expect(brToISO("2/1/2026")).toBe("2026-01-02");
    expect(brToISO("31/02/2026")).toBeNull(); // 31 de fevereiro não existe
    expect(brToISO("2026-01-02")).toBeNull(); // formato errado
  });

  it("isoToBR faz a volta", () => {
    expect(isoToBR("2026-07-03")).toBe("03/07/2026");
  });
});
