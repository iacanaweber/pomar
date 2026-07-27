import { describe, expect, it } from "vitest";
import { buildComparison } from "./comparison";

const pos = (ticker: string, asset_class: string, value: number) => ({ ticker, asset_class, value });

// carteira alvo: Ações 50% (AAA3 60% / BBB3 40%) e FIIs 50% (CCC11 100%)
// => alvos sobre o total: AAA3 30%, BBB3 20%, CCC11 50%
const TARGETS = { STOCK: 0.5, FII: 0.5, ETF: 0, BDR: 0 };
const BASKETS = {
  STOCK: { AAA3: 0.6, BBB3: 0.4 },
  FII: { CCC11: 1.0 },
};

const row = (c: ReturnType<typeof buildComparison>, ticker: string) =>
  c.rows.find((r) => r.ticker === ticker)!;

describe("buildComparison", () => {
  it("ativo exatamente no peso-alvo fica 'ok' com desvio zero", () => {
    const c = buildComparison(
      [pos("AAA3", "STOCK", 300), pos("BBB3", "STOCK", 200), pos("CCC11", "FII", 500)],
      1000,
      TARGETS,
      BASKETS,
    );
    for (const t of ["AAA3", "BBB3", "CCC11"]) {
      expect(row(c, t).deltaPp).toBe(0);
      expect(row(c, t).status).toBe("ok");
    }
    expect(c.offTargetPct).toBe(0);
  });

  it("abaixo e acima do alvo têm sinal e valor em reais corretos", () => {
    const c = buildComparison(
      [pos("AAA3", "STOCK", 100), pos("BBB3", "STOCK", 200), pos("CCC11", "FII", 700)],
      1000,
      TARGETS,
      BASKETS,
    );
    // AAA3: 10% hoje, alvo 30% => faltam 20 p.p. = R$ 200
    expect(row(c, "AAA3").currentPct).toBe(10);
    expect(row(c, "AAA3").targetPct).toBe(30);
    expect(row(c, "AAA3").deltaPp).toBe(20);
    expect(row(c, "AAA3").deltaBrl).toBe(200);
    expect(row(c, "AAA3").status).toBe("below");
    // CCC11: 70% hoje, alvo 50% => sobram 20 p.p.
    expect(row(c, "CCC11").deltaPp).toBe(-20);
    expect(row(c, "CCC11").deltaBrl).toBe(-200);
    expect(row(c, "CCC11").status).toBe("above");
  });

  it("posição fora da carteira alvo é sinalizada, não escondida", () => {
    const c = buildComparison(
      [pos("AAA3", "STOCK", 300), pos("BBB3", "STOCK", 200), pos("CCC11", "FII", 400),
       pos("LEGADO3", "STOCK", 100)],
      1000,
      TARGETS,
      BASKETS,
    );
    const legado = row(c, "LEGADO3");
    expect(legado.status).toBe("off_target");
    expect(legado.targetPct).toBe(0);
    expect(legado.currentPct).toBe(10);
    expect(legado.deltaPp).toBe(-10); // sobra tudo: não deveria estar aí
    expect(c.offTargetPct).toBe(10);
  });

  it("ativo do alvo ainda não comprado aparece com atual 0", () => {
    const c = buildComparison([pos("AAA3", "STOCK", 1000)], 1000, TARGETS, BASKETS);
    const naoComprado = row(c, "BBB3");
    expect(naoComprado.status).toBe("not_bought");
    expect(naoComprado.currentPct).toBe(0);
    expect(naoComprado.targetPct).toBe(20);
    expect(naoComprado.deltaPp).toBe(20);
    expect(naoComprado.currentValue).toBe(0);
  });

  it("ordena pelo maior desvio absoluto — o topo é o que pede decisão", () => {
    const c = buildComparison(
      [pos("AAA3", "STOCK", 295), pos("BBB3", "STOCK", 5), pos("CCC11", "FII", 700),
       pos("LEGADO3", "STOCK", 0.5)],
      1000.5,
      TARGETS,
      BASKETS,
    );
    const desvios = c.rows.map((r) => Math.abs(r.deltaPp));
    expect(desvios).toEqual([...desvios].sort((a, b) => b - a));
    // e o primeiro é de fato quem mais precisa de decisão
    expect(Math.abs(c.rows[0].deltaPp)).toBe(Math.max(...desvios));
  });

  it("agrega por classe usando a meta da classe, não a soma dos ativos", () => {
    const c = buildComparison(
      [pos("AAA3", "STOCK", 100), pos("BBB3", "STOCK", 200), pos("CCC11", "FII", 700)],
      1000,
      TARGETS,
      BASKETS,
    );
    const stock = c.byClass.find((b) => b.cls === "STOCK")!;
    expect(stock.currentPct).toBe(30); // 10 + 20
    expect(stock.targetPct).toBe(50);
    expect(stock.deltaPp).toBe(20);
    expect(stock.deltaBrl).toBe(200);
  });

  it("metas que não somam 100% não quebram a conta — só são reportadas", () => {
    const c = buildComparison(
      [pos("AAA3", "STOCK", 1000)],
      1000,
      { STOCK: 0.5, FII: 0.2, ETF: 0, BDR: 0 },
      { STOCK: { AAA3: 1.0 } },
    );
    expect(c.targetSumPct).toBe(70);
    expect(row(c, "AAA3").targetPct).toBe(50);
    expect(row(c, "AAA3").deltaPp).toBe(-50);
  });

  it("carteira sem valor não divide por zero", () => {
    const c = buildComparison([], 0, TARGETS, BASKETS);
    expect(c.rows.every((r) => Number.isFinite(r.currentPct))).toBe(true);
    expect(c.rows.every((r) => r.deltaBrl === 0)).toBe(true);
    expect(c.totalValue).toBe(0);
  });

  it("sem carteira alvo definida, avisa em vez de inventar comparação", () => {
    const c = buildComparison([pos("AAA3", "STOCK", 1000)], 1000, {}, {});
    expect(c.hasTarget).toBe(false);
    expect(row(c, "AAA3").status).toBe("off_target");
  });

  it("casa tickers em maiúsculas independentemente de como vieram", () => {
    const c = buildComparison([pos("aaa3", "STOCK", 1000)], 1000,
      { STOCK: 1.0 }, { STOCK: { aaa3: 1.0 } });
    expect(c.rows).toHaveLength(1);
    expect(row(c, "AAA3").status).toBe("ok");
  });
});
