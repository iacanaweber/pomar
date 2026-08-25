// Gera os ícones PWA do Pomar em Node puro (sem dependência): encoder PNG manual
// (assinatura, IHDR, IDAT com filtro 0, IEND, CRC32) e rasterização por teste de
// distância com superamostragem 4×4 — mesmo padrão do gen-icons.mjs do GAIA, para os
// dois projetos do autor continuarem reproduzíveis do mesmo jeito.
//
// Desenho escolhido (variação C, ver icons-src/): um FRUTO único cujo cabinho é a linha
// ascendente, com uma folha no tom claro do tema. Foi a que sobreviveu melhor ao teste
// que decide um ícone de app — 48px ao lado do GAIA na tela inicial.
//
// A GEOMETRIA VIVE AQUI e em nenhum outro lugar: o script emite tanto os PNGs quanto o
// SVG e o favicon. Manter um SVG escrito à mão em paralelo criaria duas fontes que
// divergem no primeiro ajuste de raio.
//
// Cores lidas de src/index.css (--green, --leaf, --bg). Nenhum verde novo é inventado
// aqui: mudar a paleta do app e não mudar o ícone é como eles saem de sincronia.
import { deflateSync } from 'node:zlib'
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const ICONS = join(ROOT, 'public', 'icons')
const PUBLIC = join(ROOT, 'public')

const BG = [0xf6, 0xf8, 0xf6] // --bg
const GREEN = [0x1b, 0x5e, 0x20] // --green
const LEAF = [0x66, 0xbb, 0x6a] // --leaf

// --- geometria, em coordenadas de um viewBox 512×512 -------------------------------
const FRUIT = { cx: 244, cy: 322, r: 148 }
const STEM = { p0: [250, 200], p1: [274, 146], p2: [326, 110], p3: [386, 94], width: 32 }
// A folha são duas béziers que fecham: a de cima e a de baixo do mesmo contorno.
const LEAF_TOP = { p0: [310, 142], p1: [276, 96], p2: [200, 92], p3: [164, 120] }
const LEAF_BOTTOM = { p0: [164, 120], p1: [200, 176], p2: [276, 184], p3: [310, 142] }

// Zona segura do maskable: o Android recorta o ícone na forma que o launcher quiser, e
// o conteúdo precisa caber em 80% da área. 0.72 dá folga sobre esse mínimo.
const MASKABLE_SCALE = 0.72

// A caixa do desenho não é simétrica (o cabinho puxa para cima e para a direita), então
// desenhá-lo nas coordenadas "naturais" o deixa 18px abaixo do centro do quadrado — o
// bastante para o ícone parecer torto na tela inicial ao lado dos outros. Estes valores
// centram a caixa e a levam a ~82% do lado, que é o enquadramento de um ícone de app.
const COMPOSE = { dx: 7, dy: -18, scale: 1.07 }

const bezier = ({ p0, p1, p2, p3 }, t) => {
  const mt = 1 - t
  const a = mt * mt * mt, b = 3 * mt * mt * t, c = 3 * mt * t * t, d = t * t * t
  return [
    a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
    a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1],
  ]
}

const sample = (curve, n) => Array.from({ length: n + 1 }, (_, i) => bezier(curve, i / n))

const STEM_PTS = sample(STEM, 64)
const LEAF_PTS = [...sample(LEAF_TOP, 48), ...sample(LEAF_BOTTOM, 48)]

/** Distância de um ponto ao segmento (a,b) — o núcleo do traço do cabinho. */
function distToSegment(px, py, a, b) {
  const dx = b[0] - a[0], dy = b[1] - a[1]
  const len2 = dx * dx + dy * dy
  let t = len2 === 0 ? 0 : ((px - a[0]) * dx + (py - a[1]) * dy) / len2
  t = t < 0 ? 0 : t > 1 ? 1 : t
  const cx = a[0] + t * dx, cy = a[1] + t * dy
  return Math.hypot(px - cx, py - cy)
}

function nearPolyline(px, py, pts, halfWidth) {
  for (let i = 0; i < pts.length - 1; i++) {
    if (distToSegment(px, py, pts[i], pts[i + 1]) <= halfWidth) return true
  }
  return false
}

/** Ponto dentro do polígono (regra par-ímpar) — usado para a folha. */
function insidePolygon(px, py, pts) {
  let inside = false
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const [xi, yi] = pts[i], [xj, yj] = pts[j]
    if ((yi > py) !== (yj > py) && px < ((xj - xi) * (py - yi)) / (yj - yi) + xi) inside = !inside
  }
  return inside
}

/** Cor de um ponto no viewBox, JÁ com o enquadramento de COMPOSE desfeito.
 *  Ordem de pintura = ordem do SVG: cabinho, folha, fruto (o fruto por cima). */
function colorAt(sx, sy, { mono = false } = {}) {
  const x = 256 + (sx - 256 - COMPOSE.dx) / COMPOSE.scale
  const y = 256 + (sy - 256 - COMPOSE.dy) / COMPOSE.scale
  if (Math.hypot(x - FRUIT.cx, y - FRUIT.cy) <= FRUIT.r) return GREEN
  if (insidePolygon(x, y, LEAF_PTS)) return mono ? GREEN : LEAF
  if (nearPolyline(x, y, STEM_PTS, STEM.width / 2)) return GREEN
  return null
}

// ---------- CRC32 ----------
const CRC_TABLE = new Uint32Array(256)
for (let n = 0; n < 256; n++) {
  let c = n
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
  CRC_TABLE[n] = c >>> 0
}

function crc32(buf) {
  let c = 0xffffffff
  for (let i = 0; i < buf.length; i++) c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8)
  return (c ^ 0xffffffff) >>> 0
}

function chunk(type, data) {
  const len = Buffer.alloc(4)
  len.writeUInt32BE(data.length)
  const body = Buffer.concat([Buffer.from(type, 'ascii'), data])
  const crc = Buffer.alloc(4)
  crc.writeUInt32BE(crc32(body))
  return Buffer.concat([len, body, crc])
}

function encodePNG(width, height, rgb) {
  const sig = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])
  const ihdr = Buffer.alloc(13)
  ihdr.writeUInt32BE(width, 0)
  ihdr.writeUInt32BE(height, 4)
  ihdr[8] = 8 // bit depth
  ihdr[9] = 2 // color type: truecolor RGB
  const raw = Buffer.alloc(height * (1 + width * 3))
  for (let y = 0; y < height; y++) {
    const row = y * (1 + width * 3)
    raw[row] = 0 // filtro 0
    rgb.copy(raw, row + 1, y * width * 3, (y + 1) * width * 3)
  }
  const idat = deflateSync(raw, { level: 9 })
  return Buffer.concat([sig, chunk('IHDR', ihdr), chunk('IDAT', idat), chunk('IEND', Buffer.alloc(0))])
}

// ---------- rasterização ----------
const SS = 4 // subamostras por eixo (anti-aliasing)

function draw(size, { scale = 1, mono = false } = {}) {
  const rgb = Buffer.alloc(size * size * 3)
  const k = size / 512
  const center = 256
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const acc = [0, 0, 0]
      for (let sy = 0; sy < SS; sy++) {
        for (let sx = 0; sx < SS; sx++) {
          // volta da tela para o viewBox, desfazendo a escala da zona segura
          const vx = center + ((x + (sx + 0.5) / SS) / k - center) / scale
          const vy = center + ((y + (sy + 0.5) / SS) / k - center) / scale
          const color = colorAt(vx, vy, { mono }) ?? BG
          acc[0] += color[0]; acc[1] += color[1]; acc[2] += color[2]
        }
      }
      const i = (y * size + x) * 3
      const n = SS * SS
      rgb[i] = Math.round(acc[0] / n)
      rgb[i + 1] = Math.round(acc[1] / n)
      rgb[i + 2] = Math.round(acc[2] / n)
    }
  }
  return encodePNG(size, size, rgb)
}

// ---------- SVG (mesma geometria, para o favicon vetorial e a fonte versionada) ------
const path = (c) => `M ${c.p0[0]} ${c.p0[1]} C ${c.p1[0]} ${c.p1[1]}, ${c.p2[0]} ${c.p2[1]}, ${c.p3[0]} ${c.p3[1]}`

function svg({ mono = false } = {}) {
  const green = `#${GREEN.map((v) => v.toString(16).padStart(2, '0')).join('')}`
  const leaf = mono ? green : `#${LEAF.map((v) => v.toString(16).padStart(2, '0')).join('')}`
  const bg = `#${BG.map((v) => v.toString(16).padStart(2, '0')).join('')}`
  // O mesmo enquadramento de COMPOSE, aqui como transform — para o SVG e os PNGs serem
  // literalmente o mesmo desenho.
  const t = `translate(${COMPOSE.dx} ${COMPOSE.dy}) translate(256 256) scale(${COMPOSE.scale}) translate(-256 -256)`
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512"
     role="img" aria-label="Pomar">
  <!-- GERADO por scripts/gen-icons.mjs — não edite à mão; ajuste a geometria no script. -->
  <rect width="512" height="512" fill="${bg}"/>
  <g transform="${t}">
    <path d="${path(STEM)}" fill="none" stroke="${green}" stroke-width="${STEM.width}" stroke-linecap="round"/>
    <path d="${path(LEAF_TOP)} C ${LEAF_BOTTOM.p1[0]} ${LEAF_BOTTOM.p1[1]}, ${LEAF_BOTTOM.p2[0]} ${LEAF_BOTTOM.p2[1]}, ${LEAF_BOTTOM.p3[0]} ${LEAF_BOTTOM.p3[1]} z" fill="${leaf}"/>
    <circle cx="${FRUIT.cx}" cy="${FRUIT.cy}" r="${FRUIT.r}" fill="${green}"/>
  </g>
</svg>
`
}

// ---------- saída ----------
mkdirSync(ICONS, { recursive: true })

const targets = [
  ['icon-192.png', 192, {}],
  ['icon-512.png', 512, {}],
  ['maskable-512.png', 512, { scale: MASKABLE_SCALE }],
  ['apple-touch-icon.png', 180, {}],
]
for (const [name, size, opts] of targets) {
  writeFileSync(join(ICONS, name), draw(size, opts))
  console.log(`gerado icons/${name} (${size}×${size})`)
}

// favicon: monocromático, derivado da MESMA silhueta. SVG porque ele é nítido em
// qualquer tamanho e o favicon é justamente onde o ícone fica menor.
writeFileSync(join(PUBLIC, 'favicon.svg'), svg({ mono: true }))
console.log('gerado favicon.svg (monocromático)')

writeFileSync(join(ROOT, 'icons-src', 'pomar-icon.svg'), svg())
console.log('gerado icons-src/pomar-icon.svg (fonte colorida)')
