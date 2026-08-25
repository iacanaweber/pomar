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
const legacyRow = (c: ReturnType<typeof buildComparison>, ticker: string) =>
  c.legacy.find((r) => r.ticker === ticker)!;

/** Nenhum número exibível pode ser Infinity ou NaN — é a regressão que o bloco pede. */
const finito = (c: ReturnType<typeof buildComparison>) => {
  for (const r of [...c.rows, ...c.legacy]) {
    for (const v of [r.currentPct, r.portfolioPct, r.currentValue, r.targetPct, r.targetBrl,
                     r.deltaPp, r.deltaBrl]) {
      if (v !== null) expect(Number.isFinite(v)).toBe(true);
    }
  }
  for (const b of c.byClass) {
    for (const v of [b.currentPct, b.targetPct, b.deltaPp, b.deltaBrl, b.currentValue]) {
      expect(Number.isFinite(v)).toBe(true);
    }
  }
  for (const v of [c.totalValue, c.alignedValue, c.legacyValue, c.legacyPct, c.targetBase,
                   c.targetSumPct]) {
    expect(Number.isFinite(v)).toBe(true);
  }
};

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
      expect(row(c, t).state).toBe("IN_TARGET");
    }
    expect(c.legacy).toHaveLength(0);
    expect(c.legacyPct).toBe(0);
    finito(c);
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
    finito(c);
  });

  it("ativo do alvo ainda não comprado é NEW, com atual 0", () => {
    const c = buildComparison([pos("AAA3", "STOCK", 1000)], 1000, TARGETS, BASKETS);
    const novo = row(c, "BBB3");
    expect(novo.state).toBe("NEW");
    expect(novo.currentPct).toBe(0);
    expect(novo.targetPct).toBe(20);
    expect(novo.deltaPp).toBe(20);
    expect(novo.currentValue).toBe(0);
    finito(c);
  });

  // --- o problema do 0%: os quatro casos obrigatórios ---

  describe("posições fora do alvo (LEGACY)", () => {
    it("classe com alvo 0% e posição existente não produz razão ao alvo", () => {
      const c = buildComparison(
        [pos("AAA3", "STOCK", 500), pos("CCC11", "FII", 400), pos("XPTO11", "ETF", 100)],
        1000,
        { STOCK: 0.5, FII: 0.5, ETF: 0, BDR: 0 },
        { ...BASKETS, ETF: { XPTO11: 1.0 } },
      );
      const legado = legacyRow(c, "XPTO11");
      expect(legado.state).toBe("LEGACY");
      // o ponto do bloco: alvo zero não vira epsilon, vira ausência de alvo
      expect(legado.targetPct).toBeNull();
      expect(legado.deltaPp).toBeNull();
      expect(legado.deltaBrl).toBeNull();
      expect(legado.status).toBeNull();
      // o que sobra é o que faz sentido: valor e participação no patrimônio
      expect(legado.currentValue).toBe(100);
      expect(legado.portfolioPct).toBe(10);
      finito(c);
    });

    it("ticker com posição e ausente de qualquer cesta é LEGACY", () => {
      const c = buildComparison(
        [pos("AAA3", "STOCK", 300), pos("BBB3", "STOCK", 200), pos("CCC11", "FII", 400),
         pos("LEGADO3", "STOCK", 100)],
        1000,
        TARGETS,
        BASKETS,
      );
      const legado = legacyRow(c, "LEGADO3");
      expect(legado.state).toBe("LEGACY");
      expect(legado.targetPct).toBeNull();
      expect(legado.portfolioPct).toBe(10);
      expect(c.legacyValue).toBe(100);
      expect(c.legacyPct).toBe(10);
      // e ele sai da lista principal: não polui o "desvio por ativo"
      expect(c.rows.some((r) => r.ticker === "LEGADO3")).toBe(false);
      finito(c);
    });

    it("carteira alvo vazia com posições existentes: tudo é LEGACY e nada explode", () => {
      const c = buildComparison(
        [pos("AAA3", "STOCK", 600), pos("CCC11", "FII", 400)],
        1000,
        {},
        {},
      );
      expect(c.hasTarget).toBe(false);
      expect(c.rows).toHaveLength(0);
      expect(c.legacy).toHaveLength(2);
      expect(c.legacy.every((r) => r.targetPct === null && r.deltaPp === null)).toBe(true);
      expect(c.legacyValue).toBe(1000);
      expect(c.legacyPct).toBe(100);
      expect(c.alignedValue).toBe(0);
      finito(c);
    });

    it("classe inteira com alvo 0% e várias posições: nenhuma divisão por zero", () => {
      const c = buildComparison(
        [pos("AAA3", "STOCK", 200), pos("BBB3", "STOCK", 150), pos("CCC3", "STOCK", 150),
         pos("DDD11", "FII", 500)],
        1000,
        { STOCK: 0, FII: 1.0, ETF: 0, BDR: 0 },
        { STOCK: { AAA3: 0.4, BBB3: 0.3, CCC3: 0.3 }, FII: { DDD11: 1.0 } },
      );
      expect(c.legacy.map((r) => r.ticker).sort()).toEqual(["AAA3", "BBB3", "CCC3"]);
      expect(c.legacy.every((r) => r.state === "LEGACY" && r.deltaPp === null)).toBe(true);
      expect(c.legacyValue).toBe(500);
      // o capital alinhado é só o FII, e ele está 100% dele mesmo
      expect(c.alignedValue).toBe(500);
      expect(row(c, "DDD11").currentPct).toBe(100);
      expect(row(c, "DDD11").deltaPp).toBe(0);
      finito(c);
    });

    it("denominador da comparação exclui o legado — a forma é medida sobre o alinhado", () => {
      // 500 alinhados (250 AAA3 + 250 CCC11) + 500 de legado
      const c = buildComparison(
        [pos("AAA3", "STOCK", 250), pos("CCC11", "FII", 250), pos("LEGADO3", "STOCK", 500)],
        1000,
        { STOCK: 0.5, FII: 0.5, ETF: 0, BDR: 0 },
        { STOCK: { AAA3: 1.0 }, FII: { CCC11: 1.0 } },
      );
      // sobre o patrimônio AAA3 é 25%; sobre o capital alinhado é 50% — e é 50% que interessa
      expect(row(c, "AAA3").portfolioPct).toBe(25);
      expect(row(c, "AAA3").currentPct).toBe(50);
      expect(row(c, "AAA3").deltaPp).toBe(0); // a FORMA está certa
      expect(c.alignedValue).toBe(500);
      finito(c);
    });
  });

  // --- legacy_in_total: a base dos alvos em R$ ---

  describe("legacyInTotal", () => {
    const posicoes = [pos("AAA3", "STOCK", 250), pos("CCC11", "FII", 250),
                      pos("LEGADO3", "STOCK", 500)];
    const alvos = { STOCK: 0.5, FII: 0.5, ETF: 0, BDR: 0 };
    const cestas = { STOCK: { AAA3: 1.0 }, FII: { CCC11: 1.0 } };

    it("default true: o legado entra na base e a carteira fica subalocada até a venda", () => {
      const c = buildComparison(posicoes, 1000, alvos, cestas);
      expect(c.legacyInTotal).toBe(true);
      expect(c.targetBase).toBe(1000);
      // alvo de AAA3 = 50% de 1000 = 500; tem 250 => faltam 250
      expect(row(c, "AAA3").targetBrl).toBe(500);
      expect(row(c, "AAA3").deltaBrl).toBe(250);
      // a leitura de p.p. continua dizendo que a FORMA está certa: as duas convivem
      expect(row(c, "AAA3").deltaPp).toBe(0);
      finito(c);
    });

    it("false: os alvos saem só sobre o capital alinhado", () => {
      const c = buildComparison(posicoes, 1000, alvos, cestas, { legacyInTotal: false });
      expect(c.targetBase).toBe(500);
      expect(row(c, "AAA3").targetBrl).toBe(250);
      expect(row(c, "AAA3").deltaBrl).toBe(0); // já está no alvo
      finito(c);
    });
  });

  // --- renda fixa ---

  it("a renda fixa que conta na carteira entra no patrimônio e na classe", () => {
    const c = buildComparison(
      [pos("AAA3", "STOCK", 700)],
      700,
      { STOCK: 0.7, RENDA_FIXA: 0.3 },
      { STOCK: { AAA3: 1.0 } },
      { rendaFixaValue: 300 },
    );
    expect(c.totalValue).toBe(1000);
    const rf = c.byClass.find((b) => b.cls === "RENDA_FIXA")!;
    expect(rf.currentValue).toBe(300);
    expect(rf.currentPct).toBe(30);
    expect(rf.deltaPp).toBe(0);
    finito(c);
  });

  it("posição atribuída ao bucket de renda fixa soma na classe, não vira ticker do alvo", () => {
    const c = buildComparison(
      [pos("AAA3", "STOCK", 700), pos("IMAB11", "RENDA_FIXA", 200)],
      900,
      { STOCK: 0.7, RENDA_FIXA: 0.3 },
      { STOCK: { AAA3: 1.0 } },
      { rendaFixaValue: 100 },
    );
    // IMAB11 não aparece como linha: os itens da cesta de RF são indexadores
    expect(c.rows.some((r) => r.ticker === "IMAB11")).toBe(false);
    expect(c.legacy.some((r) => r.ticker === "IMAB11")).toBe(false);
    expect(c.byClass.find((b) => b.cls === "RENDA_FIXA")!.currentValue).toBe(300);
    finito(c);
  });

  it("meta só de renda fixa já conta como carteira alvo definida", () => {
    const c = buildComparison([], 0, { RENDA_FIXA: 1.0 }, {}, { rendaFixaValue: 500 });
    expect(c.hasTarget).toBe(true);
    finito(c);
  });

  // --- agregações e bordas ---

  it("ordena pelo maior desvio absoluto — o topo é o que pede decisão", () => {
    const c = buildComparison(
      [pos("AAA3", "STOCK", 295), pos("BBB3", "STOCK", 5), pos("CCC11", "FII", 700)],
      1000,
      TARGETS,
      BASKETS,
    );
    const desvios = c.rows.map((r) => Math.abs(r.deltaPp ?? 0));
    expect(desvios).toEqual([...desvios].sort((a, b) => b - a));
    finito(c);
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
    finito(c);
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
    finito(c);
  });

  it("carteira sem valor não divide por zero", () => {
    const c = buildComparison([], 0, TARGETS, BASKETS);
    expect(c.totalValue).toBe(0);
    expect(c.alignedValue).toBe(0);
    expect(c.legacyPct).toBe(0);
    expect(c.rows.every((r) => r.currentPct === 0 && r.deltaBrl === 0)).toBe(true);
    finito(c);
  });

  it("patrimônio inteiro em legado não divide por zero no denominador alinhado", () => {
    const c = buildComparison([pos("LEGADO3", "STOCK", 1000)], 1000, TARGETS, BASKETS);
    expect(c.alignedValue).toBe(0);
    expect(c.legacyPct).toBe(100);
    // as linhas NEW existem (o alvo está definido) e não viram Infinity
    expect(c.rows.every((r) => r.state === "NEW" && r.currentPct === 0)).toBe(true);
    finito(c);
  });

  it("casa tickers em maiúsculas independentemente de como vieram", () => {
    const c = buildComparison([pos("aaa3", "STOCK", 1000)], 1000,
      { STOCK: 1.0 }, { STOCK: { aaa3: 1.0 } });
    expect(c.rows).toHaveLength(1);
    expect(row(c, "AAA3").status).toBe("ok");
    finito(c);
  });
});
