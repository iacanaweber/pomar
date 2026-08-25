import { describe, expect, it } from "vitest";
import { classify } from "./CeilingBadge";

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
