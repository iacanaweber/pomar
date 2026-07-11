import { describe, expect, it } from "vitest";
import { classify } from "./CeilingBadge";
import { streakMonths } from "./OrdersHistory";

describe("classify (chip do preço-teto)", () => {
  it("classifica pela MARGEM mesmo sem preço (falso 'não calculado' do ranking)", () => {
    expect(classify(null, null, 0.12, null).status).toBe("verde");
    expect(classify(null, null, -0.08, null).status).toBe("vermelho");
    expect(classify(null, null, 0.0, null).status).toBe("amarelo");
  });

  it("usa belowCeiling como último recurso", () => {
    expect(classify(null, null, null, true).status).toBe("verde");
    expect(classify(null, null, null, false).status).toBe("vermelho");
  });

  it("'não calculado' só quando não há informação nenhuma", () => {
    expect(classify(null, null, null, null).status).toBe("na");
  });

  it("calcula a margem de teto+preço quando ela não vem", () => {
    expect(classify(30, 20, null, null).status).toBe("verde"); // 33% abaixo do teto
    expect(classify(30, 40, null, null).status).toBe("vermelho");
  });
});

describe("streakMonths (disciplina de aportes)", () => {
  const ym = (offset: number) => {
    const d = new Date();
    const x = new Date(d.getFullYear(), d.getMonth() - offset, 15);
    return `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, "0")}-15`;
  };

  it("conta meses consecutivos terminando no atual", () => {
    expect(streakMonths([ym(0), ym(1), ym(2)])).toBe(3);
  });

  it("mês corrente sem aporte não quebra a sequência", () => {
    expect(streakMonths([ym(1), ym(2)])).toBe(2);
  });

  it("buraco no meio encerra a contagem", () => {
    expect(streakMonths([ym(0), ym(2), ym(3)])).toBe(1);
  });

  it("vazio = 0", () => {
    expect(streakMonths([])).toBe(0);
  });
});
