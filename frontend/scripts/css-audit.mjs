#!/usr/bin/env node
// Rede de segurança para mexer em `src/index.css`. O projeto não tem regressão visual —
// `npm run build` enviaria feliz um stylesheet com uma regra anulada por outra — e
// adicionar Playwright só para isso contradiz a dieta de dependências. Então: zero deps,
// rodado à mão, na convenção de `gen-icons.mjs`.
//
//   node scripts/css-audit.mjs snapshot [--resolve-tokens] > /tmp/antes.txt
//   ...mexe no CSS...
//   node scripts/css-audit.mjs snapshot [--resolve-tokens] | diff /tmp/antes.txt -
//
//   node scripts/css-audit.mjs dupes
//
// `snapshot` normaliza para «contexto|seletor -> propriedades ordenadas». As declarações
// são aplicadas em ordem de origem, com a última vencendo e com shorthand apagando os
// longhands anteriores — então o que sai é o VALOR COMPUTADO por seletor, não o texto.
// A SAÍDA é ordenada alfabeticamente, então um diff vazio é prova de que a cascata por
// seletor não mudou, mesmo que as regras tenham se movido no arquivo.
//
// DOIS LIMITES HONESTOS, porque uma rede de segurança que promete demais é pior que
// nenhuma:
//
//  1. Prova equivalência POR SELETOR, não a cascata inteira entre seletores DIFERENTES
//     que casam com o mesmo elemento. Daí a regra de operação:
//       nunca mova uma regra através de outra que compartilhe um token de classe, a
//       menos que `dupes` diga que os conjuntos de propriedades são disjuntos.
//
//  2. A lista de shorthands abaixo é a dos que aparecem neste arquivo, não a do CSS
//     inteiro. Um shorthand novo e não listado volta a ser um ponto cego.
//
// `--resolve-tokens` troca var(--x) pelo valor declarado no :root antes de comparar. É o
// que torna revisável a migração de px cru para --sp-*: sem isso, `8px` e `var(--sp-8)`
// diferem como texto e todo diff fica ruidoso.

import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const raiz = join(dirname(fileURLToPath(import.meta.url)), "..");
const modo = process.argv[2];
const resolver = process.argv.includes("--resolve-tokens");

const bruto = readFileSync(join(raiz, "src", "index.css"), "utf8");

/** Remove comentários preservando o número de linhas (para `dupes` reportar a linha certa). */
function semComentarios(css) {
  return css.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, " "));
}

/** Percorre as chaves e devolve as regras achatadas, com o contexto de at-rule junto. */
function regras(css) {
  const saida = [];
  let i = 0;
  const pilha = []; // contextos de at-rule abertos (@media, @supports, @layer)

  const linhaDe = (pos) => css.slice(0, pos).split("\n").length;

  while (i < css.length) {
    const abre = css.indexOf("{", i);
    if (abre === -1) break;
    const fecha = css.indexOf("}", i);

    // Fecha um contexto antes de abrir outro bloco: acabou uma at-rule.
    if (fecha !== -1 && fecha < abre) {
      pilha.pop();
      i = fecha + 1;
      continue;
    }

    const prelude = css.slice(i, abre).trim();
    if (prelude.startsWith("@")) {
      // At-rule com bloco. `@font-face`/`@keyframes` não participam da cascata de
      // propriedades: entram como contexto próprio e nunca se fundem com nada.
      const semBloco = /^@(font-face|keyframes|page|counter-style|font-feature-values)/.test(prelude);
      if (semBloco) {
        let profundidade = 0, j = abre;
        for (; j < css.length; j++) {
          if (css[j] === "{") profundidade++;
          else if (css[j] === "}" && --profundidade === 0) break;
        }
        // Chave própria por bloco: dois @font-face coexistem por definição e nunca se
        // fundem, então não podem aparecer como "duplicata".
        const corpoBloco = css.slice(abre + 1, j);
        const identidade =
          corpoBloco.match(/font-family\s*:\s*([^;]+)/)?.[1].trim() ?? `#${linhaDe(i)}`;
        saida.push({
          contexto: [...pilha, prelude].join(" && "),
          seletor: `(bloco ${identidade})`,
          corpo: corpoBloco,
          linha: linhaDe(i),
        });
        i = j + 1;
      } else {
        pilha.push(prelude);
        i = abre + 1;
      }
      continue;
    }

    // Regra de estilo comum.
    const fim = css.indexOf("}", abre);
    const corpo = css.slice(abre + 1, fim === -1 ? css.length : fim);
    for (const sel of prelude.split(",")) {
      const s = sel.trim().replace(/\s+/g, " ");
      if (s) saida.push({ contexto: pilha.join(" && "), seletor: s, corpo, linha: linhaDe(i) });
    }
    i = (fim === -1 ? css.length : fim) + 1;
  }
  return saida;
}

// Shorthand -> longhands que ele REESCREVE. Sem isto o detector de colisão erra
// justamente o caso mais perigoso: `padding: 24px 16px` declarado depois de
// `padding-bottom: calc(...)` zera o segundo, e como os nomes das propriedades são
// diferentes a colisão passaria despercebida. Foi assim que o rodapé deste app ficou
// embaixo da barra de abas no telefone.
const LADOS = ["top", "right", "bottom", "left"];
const SHORTHANDS = {
  padding: LADOS.map((l) => `padding-${l}`),
  margin: LADOS.map((l) => `margin-${l}`),
  inset: LADOS,
  gap: ["row-gap", "column-gap"],
  "border-radius": ["border-top-left-radius", "border-top-right-radius",
    "border-bottom-right-radius", "border-bottom-left-radius"],
  border: ["border-width", "border-style", "border-color",
    ...LADOS.map((l) => `border-${l}`)],
  background: ["background-color", "background-image", "background-position",
    "background-size", "background-repeat"],
  font: ["font-family", "font-size", "font-weight", "font-style", "line-height"],
  flex: ["flex-grow", "flex-shrink", "flex-basis"],
  overflow: ["overflow-x", "overflow-y"],
  "grid-area": ["grid-row-start", "grid-column-start", "grid-row-end", "grid-column-end"],
};

/** Tudo que declarar `prop` de fato escreve — ela mesma mais o que ela reescreve. */
function alcance(prop) {
  return [prop, ...(SHORTHANDS[prop] ?? [])];
}

/** Declarações de um corpo, na ordem de origem. Ignora blocos aninhados. */
function declaracoes(corpo) {
  const saida = [];
  for (const pedaco of corpo.split(";")) {
    const p = pedaco.trim();
    if (!p || p.includes("{")) continue;
    const dp = p.indexOf(":");
    if (dp <= 0) continue;
    saida.push([p.slice(0, dp).trim(), p.slice(dp + 1).trim().replace(/\s+/g, " ")]);
  }
  return saida;
}

const limpo = semComentarios(bruto);
const todas = regras(limpo);

// --- tabela de tokens, para --resolve-tokens ---
const tokens = new Map();
if (resolver) {
  for (const r of todas) {
    if (!r.seletor.startsWith(":root")) continue;
    for (const [prop, valor] of declaracoes(r.corpo)) {
      if (prop.startsWith("--") && !tokens.has(prop)) tokens.set(prop, valor);
    }
  }
}
function expandir(valor, profundidade = 0) {
  if (!resolver || profundidade > 8 || !valor.includes("var(")) return valor;
  const trocado = valor.replace(/var\(\s*(--[\w-]+)\s*(?:,[^)]*)?\)/g, (m, nome) =>
    tokens.has(nome) ? tokens.get(nome) : m,
  );
  return trocado === valor ? valor : expandir(trocado, profundidade + 1);
}

if (modo === "snapshot") {
  // chave -> Map(prop -> valor), última declaração vencendo (é o que a cascata faz)
  const mapa = new Map();
  for (const r of todas) {
    const chave = `${r.contexto}|${r.seletor}`;
    if (!mapa.has(chave)) mapa.set(chave, new Map());
    const alvo = mapa.get(chave);
    for (const [prop, valor] of declaracoes(r.corpo)) {
      // Um shorthand APAGA os longhands declarados antes dele — é o que faz
      // `padding: 24px 16px` anular um `padding-bottom` anterior. Sem modelar isso, o
      // snapshot guardaria as duas e não veria diferença nenhuma entre o CSS certo e o
      // errado. Processar em ordem de origem e apagar aqui é o que transforma a saída
      // numa impressão digital do VALOR COMPUTADO, e não só do texto declarado.
      for (const longhand of SHORTHANDS[prop] ?? []) alvo.delete(longhand);
      alvo.set(prop, expandir(valor));
    }
  }
  for (const chave of [...mapa.keys()].sort()) {
    const props = [...mapa.get(chave)].sort(([a], [b]) => a.localeCompare(b));
    console.log(`${chave}`);
    for (const [prop, valor] of props) console.log(`    ${prop}: ${valor}`);
  }
  process.exit(0);
}

if (modo === "dupes") {
  const porChave = new Map();
  todas.forEach((r, indice) => {
    const chave = `${r.contexto}|${r.seletor}`;
    if (!porChave.has(chave)) porChave.set(chave, []);
    porChave.get(chave).push({ ...r, indice });
  });

  const dups = [...porChave.entries()].filter(([, v]) => v.length > 1);
  console.log(`${todas.length} seletores expandidos, ${dups.length} duplicados.\n`);

  for (const [chave, ocorrencias] of dups) {
    const [ctx, sel] = chave.split("|");
    const props = ocorrencias.map((o) => new Map(declaracoes(o.corpo).map(([p, v]) => [p, expandir(v)])));

    // Colisão = duas ocorrências escrevem a mesma propriedade EFETIVA, contando o que
    // cada shorthand reescreve.
    const escritoPor = new Map(); // propriedade efetiva -> Set(índice da ocorrência)
    props.forEach((m, idx) => {
      for (const p of m.keys()) {
        for (const efetiva of alcance(p)) {
          if (!escritoPor.has(efetiva)) escritoPor.set(efetiva, new Set());
          escritoPor.get(efetiva).add(idx);
        }
      }
    });
    const colidem = [...escritoPor].filter(([, quem]) => quem.size > 1).map(([p]) => p);

    console.log(`${sel}${ctx ? `   [${ctx}]` : ""}`);
    console.log(`  linhas: ${ocorrencias.map((o) => o.linha).join(", ")}`);
    if (colidem.length === 0) {
      console.log("  colisão: NENHUMA — conjuntos disjuntos, fusão é livre");
    } else {
      for (const p of colidem) {
        // Mostra a declaração real de cada lado: pode ser a própria ou o shorthand dela.
        const lados = props.map((m) => {
          if (m.has(p)) return `${p}: ${m.get(p)}`;
          for (const [decl, valor] of m) {
            if (alcance(decl).includes(p)) return `${decl}: ${valor}`;
          }
          return null;
        });
        const presentes = lados.filter(Boolean);
        if (presentes.length < 2) continue;
        const viaShorthand = presentes.some((t) => !t.startsWith(`${p}:`));
        const iguais = new Set(presentes).size === 1;
        const nota = viaShorthand
          ? "  <-- SHORTHAND SOBRESCREVE LONGHAND"
          : iguais
            ? "  (valores idênticos)"
            : "  <-- DECIDIR";
        console.log(`  colisão em ${p}: ${presentes.join("  |  ")}${nota}`);
      }
    }

    // regras interpostas que compartilham token de classe E propriedade
    const primeiro = ocorrencias[0].indice;
    const ultimo = ocorrencias[ocorrencias.length - 1].indice;
    const classes = new Set(sel.match(/\.[\w-]+/g) ?? []);
    const props0 = new Set(props.flatMap((m) => [...m.keys()]));
    const interpostas = [];
    for (let k = primeiro + 1; k < ultimo; k++) {
      const r = todas[k];
      if (`${r.contexto}|${r.seletor}` === chave) continue;
      const compartilha = [...(r.seletor.match(/\.[\w-]+/g) ?? [])].some((c) => classes.has(c));
      if (!compartilha) continue;
      const sobrepoe = declaracoes(r.corpo).map(([p]) => p).filter((p) => props0.has(p));
      if (sobrepoe.length) interpostas.push(`${r.seletor} (l.${r.linha}) -> ${sobrepoe.join(", ")}`);
    }
    if (interpostas.length) {
      console.log("  INTERPOSTAS (a ordem importa — fundir para BAIXO):");
      for (const t of interpostas) console.log(`    ${t}`);
    }
    console.log();
  }
  process.exit(0);
}

console.error("uso: node scripts/css-audit.mjs <snapshot|dupes> [--resolve-tokens]");
process.exit(1);
