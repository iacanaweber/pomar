import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";

import { buildComparison } from "../lib/comparison";
import { Canteiro } from "./Canteiro";

/** Monta a comparação pelo caminho real — `buildComparison` é a única implementação
 *  testada do desvio, e o canteiro é view pura sobre ela. */
function comparar(
  posicoes: { ticker: string; asset_class: string; value: number }[],
  metas: Record<string, number>,
  cestas: Record<string, Record<string, number>>,
) {
  const total = posicoes.reduce((s, p) => s + p.value, 0);
  return buildComparison(posicoes, total, metas, cestas);
}

describe("Canteiro", () => {
  it("sem carteira alvo, convida a definir uma em vez de desenhar um leito vazio", () => {
    const c = comparar([{ ticker: "BOVA11", asset_class: "ETF", value: 1000 }], {}, {});
    render(<Canteiro comparison={c} />);
    expect(screen.getByRole("heading", { name: /sem carteira alvo/i })).toBeInTheDocument();
  });

  it("a legenda é uma tabela de verdade, com cabeçalho de coluna", () => {
    const c = comparar(
      [
        { ticker: "BOVA11", asset_class: "ETF", value: 600 },
        { ticker: "PETR4", asset_class: "STOCK", value: 400 },
      ],
      { ETF: 0.8, STOCK: 0.2 },
      { ETF: { BOVA11: 1 }, STOCK: { PETR4: 1 } },
    );
    render(<Canteiro comparison={c} />);
    const tabela = screen.getByRole("table");
    expect(within(tabela).getByRole("columnheader", { name: "Alvo" })).toBeInTheDocument();
    expect(within(tabela).getByRole("rowheader", { name: /ETFs/ })).toBeInTheDocument();
  });

  it("o leito descreve o desvio para leitor de tela", () => {
    const c = comparar(
      [{ ticker: "BOVA11", asset_class: "ETF", value: 1000 }],
      { ETF: 1 },
      { ETF: { BOVA11: 1 } },
    );
    render(<Canteiro comparison={c} />);
    expect(screen.getByRole("img")).toHaveAccessibleName(/ETFs 100,0% de 100,0%/);
  });

  it("classe no alvo não pede dinheiro", () => {
    const c = comparar(
      [{ ticker: "BOVA11", asset_class: "ETF", value: 1000 }],
      { ETF: 1 },
      { ETF: { BOVA11: 1 } },
    );
    render(<Canteiro comparison={c} />);
    expect(screen.getAllByText("no alvo").length).toBeGreaterThan(0);
  });

  it("classe abaixo do alvo mostra quanto falta, em reais", () => {
    const c = comparar(
      [
        { ticker: "BOVA11", asset_class: "ETF", value: 500 },
        { ticker: "PETR4", asset_class: "STOCK", value: 500 },
      ],
      { ETF: 0.9, STOCK: 0.1 },
      { ETF: { BOVA11: 1 }, STOCK: { PETR4: 1 } },
    );
    render(<Canteiro comparison={c} />);
    // 90% de 1000 = 900; tem 500; faltam 400. O ETF pede 400 e a ação sobra 400, então a
    // asserção precisa ser na LINHA certa — o valor sozinho é ambíguo.
    const linhaEtf = screen.getByRole("rowheader", { name: /ETFs/ }).closest("tr")!;
    expect(within(linhaEtf).getByText(/R\$\s*400,00/)).toBeInTheDocument();
    expect(within(linhaEtf).queryByText(/^sobra/)).toBeNull();
  });

  it("classe acima do alvo diz que SOBRA — estar acima não é erro", () => {
    const c = comparar(
      [
        { ticker: "BOVA11", asset_class: "ETF", value: 500 },
        { ticker: "PETR4", asset_class: "STOCK", value: 500 },
      ],
      { ETF: 0.9, STOCK: 0.1 },
      { ETF: { BOVA11: 1 }, STOCK: { PETR4: 1 } },
    );
    render(<Canteiro comparison={c} />);
    expect(screen.getByText(/^sobra/)).toBeInTheDocument();
  });

  it("posição sem alvo aparece FORA do canteiro, com o total", () => {
    const c = comparar(
      [
        { ticker: "BOVA11", asset_class: "ETF", value: 800 },
        { ticker: "MGLU3", asset_class: "STOCK", value: 200 },
      ],
      { ETF: 1 },
      { ETF: { BOVA11: 1 } },
    );
    render(<Canteiro comparison={c} />);
    const fora = screen.getByText(/fora do canteiro/);
    expect(fora).toHaveTextContent("MGLU3");
    expect(fora).toHaveTextContent(/R\$\s*200,00/);
  });
});
