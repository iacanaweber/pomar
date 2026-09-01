import { describe, expect, it } from "vitest";
import {
  brToISO,
  isoToBR,
  money,
  num,
  parseBRL,
  pct,
  pctPts,
  signedPct,
  signedPp,
} from "./format";

describe("separador decimal — tudo vírgula, sempre", () => {
  // O bug: `pct` devolvia ponto e sete componentes escreveram a própria cópia com
  // `.replace(".", ",")` para contornar. Resultado em tela: "R$ 32,45 · DY 8.7%".
  it("pct recebe FRAÇÃO e devolve vírgula", () => {
    expect(pct(0.087)).toBe("8,7%");
    expect(pct(0.123, 2)).toBe("12,30%");
    expect(pct(0)).toBe("0,0%");
    expect(pct(1)).toBe("100,0%");
  });

  it("pctPts recebe valor JÁ em pontos percentuais", () => {
    expect(pctPts(8.7)).toBe("8,7%");
    expect(pctPts(12.3, 2)).toBe("12,30%");
    // a distinção existe justamente para não multiplicar por 100 duas vezes
    expect(pctPts(0.087)).not.toBe(pct(0.087));
  });

  it("num não põe unidade nem separador de milhar", () => {
    expect(num(12.345)).toBe("12,35");
    expect(num(1234.5, 1)).toBe("1234,5");
    expect(num(0, 0)).toBe("0");
  });

  it("money usa pt-BR com vírgula e milhar", () => {
    // O Intl separa "R$" do número com espaço NÃO-QUEBRÁVEL (U+00A0), não espaço comum —
    // é o que impede a moeda de ficar órfã no fim da linha.
    expect(money(1234.56)).toBe("R$ 1.234,56");
    expect(money(0)).toBe("R$ 0,00");
    expect(money(1234.56, "USD")).toBe("US$ 1.234,56");
  });

  it("money e parseBRL fecham o ciclo", () => {
    const ida = money(1234.56).replace(/[^\d.,]/g, "");
    expect(parseBRL(ida)).toBe(1234.56);
  });
});

describe("sinal — menos é U+2212, não hífen", () => {
  it("signedPct trabalha em fração e trata ausência de dado", () => {
    expect(signedPct(0.087)).toBe("+8,7%");
    expect(signedPct(-0.087)).toBe("−8,7%");
    expect(signedPct(0)).toBe("0,0%"); // zero não leva sinal
    expect(signedPct(null)).toBe("—");
    expect(signedPct(undefined)).toBe("—");
  });

  it("signedPp trabalha em pontos percentuais e carrega a unidade", () => {
    expect(signedPp(2.3)).toBe("+2,3 p.p.");
    expect(signedPp(-2.3)).toBe("−2,3 p.p.");
    expect(signedPp(0)).toBe("0,0 p.p.");
    expect(signedPp(12.34, 2)).toBe("+12,34 p.p.");
  });

  it("o menos é o sinal matemático, que alinha com dígitos tabulares", () => {
    expect(signedPct(-0.5)).toContain("−");
    expect(signedPct(-0.5)).not.toContain("-");
  });
});

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
