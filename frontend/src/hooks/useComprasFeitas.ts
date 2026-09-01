import { useCallback, useState } from "react";

/** Quais compras do plano atual você já executou na corretora.
 *
 *  É um checklist DESCARTÁVEL, não um registro. A posição oficial é o Ghostfolio — o app
 *  não faz tracking e não guarda ordem nenhuma. Isto existe só para o momento do aporte:
 *  com seis compras a fazer em duas abas da corretora, saber quais faltam é o que evita
 *  comprar duas vezes ou esquecer uma.
 *
 *  Escopo por plano: gerar plano novo começa com a lista limpa, porque é um aporte novo.
 *  Ao gravar, as chaves de outros planos são apagadas — senão o armazenamento cresceria
 *  um item por plano, para sempre.
 *
 *  `localStorage` com guarda, como `useTheme` e a Reserva já fazem: onde o armazenamento
 *  lança (modo privado, cota estourada), a leitura sem try/catch dentro de um
 *  inicializador de `useState` derruba a página inteira no ErrorBoundary.
 */

const PREFIXO = "pomar:comprei:";

const chaveDe = (planId: number | null | undefined) =>
  planId == null ? null : `${PREFIXO}${planId}`;

function ler(chave: string | null): string[] {
  if (!chave) return [];
  try {
    const bruto = localStorage.getItem(chave);
    if (!bruto) return [];
    const v: unknown = JSON.parse(bruto);
    return Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : [];
  } catch {
    // JSON corrompido ou storage indisponível: começa vazio, que é inofensivo.
    return [];
  }
}

function gravar(chave: string | null, tickers: string[]): void {
  if (!chave) return;
  try {
    // Só o plano atual sobrevive: um item por plano gerado cresceria sem limite.
    for (let i = localStorage.length - 1; i >= 0; i--) {
      const k = localStorage.key(i);
      if (k && k.startsWith(PREFIXO) && k !== chave) localStorage.removeItem(k);
    }
    if (tickers.length === 0) localStorage.removeItem(chave);
    else localStorage.setItem(chave, JSON.stringify(tickers));
  } catch {
    // Sem armazenamento os tiques valem só para esta sessão. É o pior caso aceitável.
  }
}

export interface ComprasFeitas {
  feito: (ticker: string) => boolean;
  alternar: (ticker: string) => void;
  /** Quantos tickers estão marcados — para o contador "2 de 4 feitas". */
  quantidade: number;
}

export function useComprasFeitas(planId: number | null | undefined): ComprasFeitas {
  const chave = chaveDe(planId);
  // A chave entra no estado inicial: trocar de plano remonta o componente com a lista do
  // plano novo, sem efeito de sincronização.
  const [estado, setEstado] = useState<{ chave: string | null; tickers: string[] }>(() => ({
    chave,
    tickers: ler(chave),
  }));

  const tickers = estado.chave === chave ? estado.tickers : ler(chave);

  const alternar = useCallback(
    (ticker: string) => {
      const t = ticker.toUpperCase();
      setEstado((atual) => {
        const base = atual.chave === chave ? atual.tickers : ler(chave);
        const proximo = base.includes(t) ? base.filter((x) => x !== t) : [...base, t];
        gravar(chave, proximo);
        return { chave, tickers: proximo };
      });
    },
    [chave],
  );

  const feito = useCallback((ticker: string) => tickers.includes(ticker.toUpperCase()), [tickers]);

  return { feito, alternar, quantidade: tickers.length };
}
