#!/usr/bin/env node
// Levanta os codepoints que o app realmente escreve e grava `font-charset.txt`, que é a
// entrada do subset das fontes (ver README).
//
// Por que derivar em vez de colar a faixa "latin" do Google: ela não tem "→" (U+2192) nem
// "−" (U+2212), que o app usa às dezenas, e tem centenas de codepoints que ele nunca
// escreve. Aqui a lista é medida, não estimada.
//
// Zero dependências, na convenção de `gen-icons.mjs`: rodado à mão, não entra no build.
//
//   node scripts/font-charset.mjs
//
// Comentários e nomes de identificador NÃO contam — só texto que pode chegar à tela.
// Como distinguir isso sem um parser de verdade é impossível, o filtro é grosseiro de
// propósito: tudo que não for ASCII imprimível entra, venha de onde vier. Um codepoint a
// mais custa alguns bytes; um a menos é um caractere que rende na fonte errada.

import { readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { join, dirname, extname } from "node:path";
import { fileURLToPath } from "node:url";

const raiz = join(dirname(fileURLToPath(import.meta.url)), "..");
const EXTENSOES = new Set([".ts", ".tsx", ".css", ".html"]);

function arquivos(dir) {
  const saida = [];
  for (const nome of readdirSync(dir)) {
    if (nome === "node_modules" || nome === "dist" || nome.startsWith(".")) continue;
    const caminho = join(dir, nome);
    if (statSync(caminho).isDirectory()) saida.push(...arquivos(caminho));
    else if (EXTENSOES.has(extname(nome))) saida.push(caminho);
  }
  return saida;
}

// `schema.d.ts` é gerado do OpenAPI e só contém descrição de campo do backend em
// comentário TypeScript — nada dali chega à tela.
const alvos = [...arquivos(join(raiz, "src")), join(raiz, "index.html")].filter(
  (c) => !c.endsWith("schema.d.ts"),
);

// ASCII imprimível inteiro é piso: é o que compõe ticker, número e a maior parte da UI.
const pontos = new Set();
for (let c = 0x20; c <= 0x7e; c++) pontos.add(c);

const naoAscii = new Map(); // codepoint -> primeiro arquivo onde apareceu
for (const caminho of alvos) {
  const texto = readFileSync(caminho, "utf8");
  for (const ch of texto) {
    const cp = ch.codePointAt(0);
    if (cp < 0x20 || (cp >= 0x7f && cp <= 0x9f)) continue; // controles
    if (cp <= 0x7e) continue; // já no piso
    pontos.add(cp);
    if (!naoAscii.has(cp)) naoAscii.set(cp, caminho.slice(raiz.length + 1));
  }
}

const ordenados = [...pontos].sort((a, b) => a - b);
const hex = (cp) => `U+${cp.toString(16).toUpperCase().padStart(4, "0")}`;

const linhas = [
  "# Gerado por scripts/font-charset.mjs — não editar à mão.",
  "# Um codepoint por linha. Entrada de --unicodes-file do pyftsubset.",
  `# ${ordenados.length} codepoints (${ordenados.length - 95} além do ASCII imprimível).`,
  "",
  ...ordenados.map((cp) => hex(cp)),
];
writeFileSync(join(raiz, "scripts", "font-charset.txt"), linhas.join("\n") + "\n");

console.log(`${ordenados.length} codepoints -> scripts/font-charset.txt`);
console.log(`\nAlém do ASCII (${naoAscii.size}):`);
for (const cp of [...naoAscii.keys()].sort((a, b) => a - b)) {
  console.log(`  ${hex(cp).padEnd(8)} ${String.fromCodePoint(cp).padEnd(3)} ${naoAscii.get(cp)}`);
}
