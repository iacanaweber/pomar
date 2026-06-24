import { useState } from "react";

export interface Slice {
  label: string;
  value: number;
  color: string;
}

const brl = (v: number) =>
  v.toLocaleString("pt-br", { style: "currency", currency: "BRL" });

function polar(cx: number, cy: number, r: number, angleDeg: number): [number, number] {
  const a = ((angleDeg - 90) * Math.PI) / 180;
  return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
}

function arc(cx: number, cy: number, rO: number, rI: number, a0: number, a1: number) {
  const [x1, y1] = polar(cx, cy, rO, a0);
  const [x2, y2] = polar(cx, cy, rO, a1);
  const [x3, y3] = polar(cx, cy, rI, a1);
  const [x4, y4] = polar(cx, cy, rI, a0);
  const large = a1 - a0 > 180 ? 1 : 0;
  return `M ${x1} ${y1} A ${rO} ${rO} 0 ${large} 1 ${x2} ${y2} L ${x3} ${y3} A ${rI} ${rI} 0 ${large} 0 ${x4} ${y4} Z`;
}

/** Donut interativo: passar o mouse/tocar destaca a fatia e mostra valor e % no centro. */
export function PieChart({
  slices,
  active,
  onActive,
  ariaLabel,
}: {
  slices: Slice[];
  active: number | null;
  onActive: (i: number | null) => void;
  ariaLabel?: string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const sel = active ?? hover;
  const size = 240;
  const cx = size / 2;
  const cy = size / 2;
  const rO = 110;
  const rI = 66;
  const total = slices.reduce((s, x) => s + x.value, 0) || 1;

  const cur = sel != null ? slices[sel] : null;
  const single = slices.length === 1;

  let angle = 0;
  return (
    <div className="pie">
      <svg
        viewBox={`0 0 ${size} ${size}`}
        className="pie-svg"
        role="img"
        aria-label={ariaLabel ?? "Distribuição da carteira"}
      >
        {single ? (
          <circle
            cx={cx}
            cy={cy}
            r={(rO + rI) / 2}
            fill="none"
            stroke={slices[0].color}
            strokeWidth={rO - rI}
          />
        ) : (
          slices.map((s, i) => {
            const span = (s.value / total) * 360;
            const a0 = angle;
            const a1 = angle + span;
            angle = a1;
            const isSel = sel === i;
            const [mx, my] = polar(0, 0, isSel ? 8 : 0, (a0 + a1) / 2);
            return (
              <path
                key={s.label}
                d={arc(cx, cy, rO, rI, a0, a1)}
                fill={s.color}
                opacity={sel == null || isSel ? 1 : 0.45}
                transform={`translate(${mx} ${my})`}
                style={{ transition: "opacity .15s, transform .15s", cursor: "pointer" }}
                onMouseEnter={() => setHover(i)}
                onMouseLeave={() => setHover(null)}
                onClick={() => onActive(active === i ? null : i)}
              />
            );
          })
        )}
        <text x={cx} y={cy - 8} textAnchor="middle" className="pie-center-label">
          {cur ? cur.label : "Total"}
        </text>
        <text x={cx} y={cy + 14} textAnchor="middle" className="pie-center-value">
          {cur ? brl(cur.value) : brl(total)}
        </text>
        {cur && (
          <text x={cx} y={cy + 32} textAnchor="middle" className="pie-center-pct">
            {((cur.value / total) * 100).toFixed(1)}%
          </text>
        )}
      </svg>
    </div>
  );
}
