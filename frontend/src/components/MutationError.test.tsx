import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { ApiError } from "../api/client";
import { MutationError } from "./MutationError";

// A regressão que estes testes protegem: dez das catorze mutações do app não
// renderizavam erro nenhum. Em /alvo isso era perda de dados sem aviso.
describe("MutationError", () => {
  it("não ocupa espaço quando não houve erro", () => {
    const { container } = render(<MutationError error={null} acao="salvar as metas" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("anuncia como alert — é consequência de uma ação, não um carregamento", () => {
    render(<MutationError error={new Error("boom")} acao="salvar as metas" />);
    expect(screen.getByRole("alert")).toHaveTextContent("Não foi possível salvar as metas.");
  });

  it("mostra a mensagem traduzida quando o erro é da API", () => {
    const erro = new ApiError(503, "Serviço indisponível", "raw");
    render(<MutationError error={erro} acao="registrar a compra" />);
    const alerta = screen.getByRole("alert");
    expect(alerta).toHaveTextContent("Não foi possível registrar a compra.");
    expect(alerta).toHaveTextContent("Serviço indisponível");
  });

  it("não vaza detalhe interno de um erro que não é da API", () => {
    render(<MutationError error={new Error("TypeError: undefined is not a function")} acao="x" />);
    expect(screen.getByRole("alert")).not.toHaveTextContent("undefined is not a function");
  });
});
