// Dicionários de rótulo da Reserva. Moravam soltos no meio do arquivo de 867 linhas,
// entre os componentes que os consomem.

export const ENTRY_LABEL: Record<string, string> = {
  balance: "Saldo",
  deposit: "Aporte",
  withdrawal: "Resgate",
};

export const KIND_LABEL: Record<string, string> = {
  cdb: "CDB",
  tesouro: "Tesouro",
  poupanca: "Poupança",
  conta: "Conta",
  outro: "Outro",
};

export const PURPOSE_LABEL: Record<string, string> = {
  investment: "Investimento",
  earmarked: "Reservado para outro fim",
};

export const LIQUIDITY_LABEL: Record<string, string> = {
  immediate: "Resgate imediato",
  scheduled: "Janela ou vencimento",
  locked: "Carência",
  unknown: "Liquidez não informada",
};
