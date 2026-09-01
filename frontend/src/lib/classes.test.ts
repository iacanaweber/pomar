import { describe, expect, it } from "vitest";
import { ALLOCATION_CLASSES, byWeightDesc } from "./classes";

describe("byWeightDesc", () => {
  it("põe o que pesa mais na frente", () => {
    const pesos: Record<string, number> = {
      STOCK: 0,
      FII: 0.05,
      ETF: 0.45,
      BDR: 0,
      RENDA_FIXA: 0.5,
    };
    expect(byWeightDesc(ALLOCATION_CLASSES, (c) => pesos[c])).toEqual([
      "RENDA_FIXA",
      "ETF",
      "FII",
      "STOCK",
      "BDR",
    ]);
  });

  it("empata pela ordem canônica, não por acaso", () => {
    // STOCK e BDR estão ambos em 0%: têm que sair na ordem de entrada, sempre a mesma.
    // Sem desempate estável, a lista embaralharia sozinha entre renders com o mesmo dado.
    const pesos: Record<string, number> = { STOCK: 0, FII: 0, ETF: 0, BDR: 0, RENDA_FIXA: 0 };
    expect(byWeightDesc(ALLOCATION_CLASSES, (c) => pesos[c])).toEqual([...ALLOCATION_CLASSES]);
  });

  it("é idempotente: reordenar o resultado não muda nada", () => {
    const pesos: Record<string, number> = { STOCK: 0.2, FII: 0.2, ETF: 0.6, BDR: 0, RENDA_FIXA: 0 };
    const uma = byWeightDesc(ALLOCATION_CLASSES, (c) => pesos[c]);
    expect(byWeightDesc(uma, (c) => pesos[c])).toEqual(uma);
  });

  it("não muta a entrada", () => {
    const antes = [...ALLOCATION_CLASSES];
    byWeightDesc(ALLOCATION_CLASSES, () => Math.random());
    expect([...ALLOCATION_CLASSES]).toEqual(antes);
  });

  it("trata peso ausente como zero, sem quebrar", () => {
    const pesos: Record<string, number> = { ETF: 1 };
    expect(byWeightDesc(ALLOCATION_CLASSES, (c) => pesos[c])[0]).toBe("ETF");
  });

  it("serve para qualquer peso, não só meta — aqui o módulo do desvio", () => {
    const linhas = [
      { cls: "STOCK", deltaPp: -1 },
      { cls: "FII", deltaPp: 8 },
      { cls: "ETF", deltaPp: -12 },
    ];
    expect(byWeightDesc(linhas, (l) => Math.abs(l.deltaPp)).map((l) => l.cls)).toEqual([
      "ETF",
      "FII",
      "STOCK",
    ]);
  });
});
