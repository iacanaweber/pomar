import type { SVGProps } from "react";

/** Ícones do Pomar. Zero dependência: um <path> por ícone, todos na MESMA grade.
 *
 *  Grade 24×24, traço 1.75, `fill: none`, cor por `currentColor` — o ícone herda a cor do
 *  texto ao lado e funciona nos dois temas sem uma linha de CSS por tema. Traço 2/24 a 20px
 *  de renderização dá ~1,67px e pesa demais ao lado de um rótulo de 11px; 1.75 fica no ponto
 *  e sobrevive ao dark mode, onde traço fino engorda opticamente.
 *
 *  REGRA DO SISTEMA: ícone só existe onde a AÇÃO NÃO TEM RÓTULO (barra inferior em 360px,
 *  botão de 44×44) ou onde o glifo é o único canal além da cor (alerta, disclosure). Botão
 *  com verbo escrito NÃO leva ícone — emoji em CTA era o que fazia a interface parecer
 *  gerada, e "Salvar" já é o rótulo de si mesmo.
 */
const PATHS = {
  // --- Navegação: silhuetas que se distinguem a 20px, sem detalhe interno ---
  // Broto: caule + duas folhas. É a marca reduzida ao que sobrevive nesse tamanho.
  plant:
    "M12 21v-7M12 14c0-3.3 2.7-6 6-6 0 3.3-2.7 6-6 6ZM12 14c0-2.8-2.2-5-5-5 0 2.8 2.2 5 5 5Z",
  basket: "M3 9h18l-1.7 9.3a2 2 0 0 1-2 1.7H6.7a2 2 0 0 1-2-1.7L3 9ZM8 9 10.5 4M16 9 13.5 4",
  vault: "M12 3 3 8.5h18L12 3ZM5.5 11v6M10 11v6M14 11v6M18.5 11v6M3 20h18",
  search: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14ZM20 20l-4.2-4.2",
  // Alvo: dois anéis e o centro. O canteiro é o desenho; esta aba é onde ele se define.
  target: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM12 16.5a4.5 4.5 0 1 0 0-9 4.5 4.5 0 0 0 0 9ZM12 13.2a1.2 1.2 0 1 0 0-2.4 1.2 1.2 0 0 0 0 2.4Z",

  // --- Sistema ---
  /* UMA direção desenhada. O estado aberto é ROTAÇÃO por CSS, não outro glifo — é isso
     que garante que o chevron signifique disclosure e mais nada no app inteiro. Antes o
     mesmo ▲/▼ era acordeão, variação de preço E bullet de red flag. */
  chevron: "m6 9 6 6 6-6",
  alert:
    "M12 9v4M12 17h.01M10.3 3.9 2.4 17.5A2 2 0 0 0 4.1 20.5h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z",
  info: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM12 11v5M12 8h.01",
  close: "M6 6l12 12M18 6 6 18",
  trash:
    "M4 7h16M10 11v6M14 11v6M6 7l1 12.1a2 2 0 0 0 2 1.9h6a2 2 0 0 0 2-1.9L18 7M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2",
  pencil: "M4 20h4L20 8a2.8 2.8 0 0 0-4-4L4 16v4ZM14.5 5.5l4 4",
  sun: "M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10ZM12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4",
  moon: "M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5Z",
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({
  name,
  size = 18,
  ...rest
}: { name: IconName; size?: number } & SVGProps<SVGSVGElement>) {
  return (
    <svg
      className={`icon icon-${name}`}
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      <path d={PATHS[name]} />
    </svg>
  );
}

/** Marca do Pomar — fruto, cabinho e folha.
 *
 *  MESMA geometria de scripts/gen-icons.mjs, que continua sendo a fonte: mexeu aqui, mexe
 *  lá. Única diferença: o cabinho vem com traço 44 em vez de 32, porque 32/512 desaparece
 *  abaixo de 32px de renderização. As cores saem de tokens, então a marca responde ao dark
 *  mode — coisa que o emoji 🌳 que ela substitui nunca fez.
 */
export function BrandMark({ size = 26 }: { size?: number }) {
  return (
    <svg viewBox="0 0 512 512" width={size} height={size} role="img" aria-label="Pomar">
      <g transform="translate(7 -18) translate(256 256) scale(1.07) translate(-256 -256)">
        <path
          d="M 250 200 C 274 146, 326 110, 386 94"
          fill="none"
          stroke="var(--green)"
          strokeWidth="44"
          strokeLinecap="round"
        />
        <path
          d="M 310 142 C 276 96, 200 92, 164 120 C 200 176, 276 184, 310 142 z"
          fill="var(--green)"
        />
        <circle cx="244" cy="322" r="148" fill="var(--green)" />
      </g>
    </svg>
  );
}
