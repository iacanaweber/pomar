import { describe, expect, it } from "vitest";
import {
  applySnap,
  distributeEvenly,
  fromCurrentValues,
  pctToShare,
  scaleTo100,
  shareOfTotal,
  shareToPct,
  snapPointFor,
  SNAP_TOLERANCE,
  sumOk,
  sumPct,
  sumState,
  type Row,
} from "./basket";

const rows = (...pcts: number[]): Row[] => pcts.map((pct, i) => ({ ticker: `T${i}`, pct }));

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

describe("snapPointFor", () => {
  it("é 100 menos a soma dos OUTROS", () => {
    // soma 110: para fechar, o índice 0 precisa cair de 60 para 50
    expect(snapPointFor(rows(60, 30, 20), 0)).toBe(50);
    expect(snapPointFor(rows(60, 30, 20), 1)).toBe(20);
    // soma 80: o índice 0 precisa subir
    expect(snapPointFor(rows(40, 20, 20), 0)).toBe(60);
  });

  it("não se move quando só o próprio peso muda — é o que segura a marca durante o arraste", () => {
    const alvo = snapPointFor(rows(60, 30, 20), 0);
    for (const v of [0, 12.5, 47, 99.99]) {
      expect(snapPointFor(rows(v, 30, 20), 0)).toBe(alvo);
    }
  });

  it("some quando a soma já fecha 100", () => {
    expect(snapPointFor(rows(50, 30, 20), 0)).toBeNull();
    expect(snapPointFor(rows(50, 30, 20), 2)).toBeNull();
    // dentro da tolerância de 0,1 p.p. também conta como fechado
    expect(snapPointFor(rows(50.05, 30, 20), 0)).toBeNull();
  });

  it("some quando o alvo é inalcançável", () => {
    // soma 150: zerar o ativo de 10% ainda deixaria 140 — nem no 0 este slider fecha a conta
    expect(snapPointFor(rows(140, 10), 1)).toBeNull();
    // mas o companheiro dele consegue: 100 − 10 = 90
    expect(snapPointFor(rows(140, 10), 0)).toBe(90);
    // soma muito baixa ainda é alcançável enquanto o alvo couber em 100
    expect(snapPointFor(rows(10, 5), 0)).toBe(95);
  });

  it("índice inexistente devolve null em vez de quebrar", () => {
    expect(snapPointFor(rows(50, 50), 7)).toBeNull();
    expect(snapPointFor([], 0)).toBeNull();
  });
});

describe("applySnap", () => {
  it("gruda dentro da tolerância", () => {
    expect(applySnap(48, 50)).toBe(50);
    expect(applySnap(52.4, 50)).toBe(50);
    expect(applySnap(50 - SNAP_TOLERANCE, 50)).toBe(50);
  });

  it("não gruda fora da tolerância", () => {
    expect(applySnap(46, 50)).toBe(46);
    expect(applySnap(55, 50)).toBe(55);
  });

  it("sem ponto magnético só arredonda", () => {
    expect(applySnap(33.333, null)).toBe(33.33);
  });
});

describe("teto do aporte para o piso (pctToShare / shareToPct)", () => {
  it("converte nos dois sentidos", () => {
    expect(pctToShare(50)).toBe(0.5);
    expect(shareToPct(0.25)).toBe(25);
    expect(shareToPct(pctToShare(35))).toBe(35);
  });

  it("zero sobrevive — 0% é uma escolha, não ausência de valor", () => {
    expect(pctToShare(0)).toBe(0);
    expect(shareToPct(0)).toBe(0);
  });

  it("grampeia fora da faixa em vez de mandar lixo ao backend", () => {
    expect(pctToShare(140)).toBe(1);
    expect(pctToShare(-3)).toBe(0);
    expect(shareToPct(1.4)).toBe(100);
    expect(shareToPct(-0.2)).toBe(0);
  });

  it("valor ausente vira 100% — o comportamento de sempre, não um teto surpresa", () => {
    expect(shareToPct(undefined)).toBe(100);
    expect(shareToPct(null)).toBe(100);
    expect(pctToShare(Number.NaN)).toBe(1);
  });
});
