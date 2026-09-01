import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";

import { buildComparison } from "../lib/comparison";
import { HojeVsAlvo } from "./HojeVsAlvo";

/** Carteira com legado: 400 em ações fora de qualquer cesta, 600 em ETF no alvo. */
const comLegado = () =>
  buildComparison(
    [
      { ticker: "MGLU3", asset_class: "STOCK", value: 250 },
      { ticker: "PETR4", asset_class: "STOCK", value: 150 },
      { ticker: "BOVA11", asset_class: "ETF", value: 600 },
    ],
    1000,
    { STOCK: 0, FII: 0, ETF: 1.0, BDR: 0 },
    { ETF: { BOVA11: 1.0 } },
  );

const linha = (nome: RegExp) => screen.getByRole("rowheader", { name: nome }).closest("tr")!;

describe("HojeVsAlvo", () => {
  it("sem carteira alvo, convida a definir uma", () => {
    const c = buildComparison(
      [{ ticker: "BOVA11", asset_class: "ETF", value: 1000 }],
      1000,
      {},
      {},
    );
    render(<HojeVsAlvo comparison={c} />);
    expect(screen.getByRole("heading", { name: /sem carteira alvo/i })).toBeInTheDocument();
  });

  // A regressão: ações fora do alvo sumiam das duas telas de comparação. Elas existem,
  // são parte da carteira, e a composição de HOJE tem de mostrá-las.
  it("classe sem alvo aparece na tabela, com o peso real", () => {
    render(<HojeVsAlvo comparison={comLegado()} />);
    const acoes = linha(/Ações/);
    expect(within(acoes).getByText("40,0%")).toBeInTheDocument(); // Hoje
    expect(within(acoes).getByText("0,0%")).toBeInTheDocument(); // Alvo
  });

  it("classe sem alvo diz que SOBRA — não é erro, é informação", () => {
    render(<HojeVsAlvo comparison={comLegado()} />);
    expect(within(linha(/Ações/)).getByText(/^sobra/)).toBeInTheDocument();
  });

  it("o desvio subtrai as próprias colunas: 40% hoje contra 0% no alvo é +40 p.p.", () => {
    render(<HojeVsAlvo comparison={comLegado()} />);
    expect(within(linha(/Ações/)).getByText("+40,0 p.p.")).toBeInTheDocument();
  });

  it("a classe com alvo não é mais inflada pelo legado", () => {
    render(<HojeVsAlvo comparison={comLegado()} />);
    // 600 de 1000 de patrimônio. Sobre o capital alinhado daria 100% — a leitura
    // otimista que fazia o ETF parecer já no lugar.
    expect(within(linha(/ETFs/)).getByText("60,0%")).toBeInTheDocument();
  });

  it("a barra Hoje mede o patrimônio inteiro; a de Alvo, as metas", () => {
    render(<HojeVsAlvo comparison={comLegado()} />);
    expect(screen.getByRole("img", { name: /^Hoje:/ })).toHaveAccessibleName(/R\$\s*1\.000,00/);
    expect(screen.getByRole("img", { name: /^Alvo:/ })).toHaveAccessibleName(/metas somam 100%/);
  });

  it("avisa que o legado aparece em Hoje e não em Alvo", () => {
    render(<HojeVsAlvo comparison={comLegado()} />);
    expect(screen.getByText(/sem alvo definido/)).toHaveTextContent(/R\$\s*400,00/);
  });

  it("a cobertura do legado é opcional e só entra quando o plano calculou", () => {
    const { rerender } = render(<HojeVsAlvo comparison={comLegado()} />);
    expect(screen.queryByText(/Vender tudo cobriria/)).toBeNull();
    rerender(<HojeVsAlvo comparison={comLegado()} coberturaLegado={0.5} gapLegado={800} />);
    expect(screen.getByText(/Vender tudo cobriria/)).toBeInTheDocument();
  });
});
