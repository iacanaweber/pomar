import { describe, expect, it } from "vitest";
import {
  distributeEvenly,
  fromCurrentValues,
  scaleTo100,
  shareOfTotal,
  sumOk,
  sumPct,
  sumState,
  type Row,
} from "./basket";

const rows = (...pcts: number[]): Row[] =>
  pcts.map((pct, i) => ({ ticker: `T${i}`, pct }));

describe("scaleTo100", () => {
  it("preserva as proporções relativas ao cortar o excesso", () => {
    const out = scaleTo100(rows(60, 30, 30)); // soma 120
    expect(out.map((r) => r.pct)).toEqual([50, 25, 25]);
    // proporção 2:1:1 mantida
    expect(out[0].pct / out[1].pct).toBe(2);
  });

  it("também sobe quando a soma está abaixo de 100", () => {
    const out = scaleTo100(rows(20, 10, 10)); // soma 40
    expect(sumPct(out)).toBe(100);
    expect(out[0].pct / out[1].pct).toBe(2);
  });

  it("fecha exatamente 100,00 mesmo com resíduo de arredondamento", () => {
    const out = scaleTo100(rows(33.33, 33.33, 33.33));
    expect(sumPct(out)).toBe(100);
    expect(sumOk(out)).toBe(true);
  });

  it("nunca zera nem torna negativo um peso pequeno", () => {
    const out = scaleTo100(rows(95, 0.5, 0.5)); // subtrair igualmente afundaria os menores
    expect(out.every((r) => r.pct > 0)).toBe(true);
    expect(sumPct(out)).toBe(100);
  });

  it("soma zero não tem proporção a preservar: divide igualmente", () => {
    expect(scaleTo100(rows(0, 0, 0, 0)).map((r) => r.pct)).toEqual([25, 25, 25, 25]);
  });

  it("lista vazia continua vazia", () => {
    expect(scaleTo100([])).toEqual([]);
  });
});

describe("distributeEvenly", () => {
  it("divide igualmente e fecha 100 mesmo com dízima", () => {
    const out = distributeEvenly(rows(80, 10, 10));
    expect(sumPct(out)).toBe(100);
    expect(out[1].pct).toBe(33.33);
    expect(out[0].pct).toBe(33.34); // o resíduo vai para o maior
  });
});

describe("sumState", () => {
  it("classifica acima, abaixo e fechado", () => {
    expect(sumState(rows(60, 50))).toBe("over");
    expect(sumState(rows(30, 20))).toBe("under");
    expect(sumState(rows(50, 50))).toBe("ok");
  });

  it("respeita a tolerância de 0,1 p.p. do backend", () => {
    expect(sumState(rows(99.95))).toBe("ok");
    expect(sumState(rows(100.05))).toBe("ok");
    expect(sumState(rows(100.2))).toBe("over");
  });

  it("cesta vazia não acusa erro", () => {
    expect(sumState([])).toBe("ok");
  });
});

describe("shareOfTotal", () => {
  it("multiplica a meta da classe pelo peso na cesta", () => {
    // ação vale 20% das ações; ações são 50% do total => 10% do total
    expect(shareOfTotal(50, 20)).toBe(10);
    expect(shareOfTotal(50, 22.08)).toBe(11.04);
    expect(shareOfTotal(0, 100)).toBe(0); // classe zerada não ocupa nada
  });
});

describe("fromCurrentValues", () => {
  it("converte valores em pesos ordenados que somam 100", () => {
    const out = fromCurrentValues([
      { ticker: "A", value: 1000 },
      { ticker: "B", value: 3000 },
    ]);
    expect(out.map((r) => r.ticker)).toEqual(["B", "A"]); // maior primeiro
    expect(out.map((r) => r.pct)).toEqual([75, 25]);
    expect(sumPct(out)).toBe(100);
  });

  it("carteira vazia ou sem valor devolve lista vazia", () => {
    expect(fromCurrentValues([])).toEqual([]);
    expect(fromCurrentValues([{ ticker: "A", value: 0 }])).toEqual([]);
  });
});
