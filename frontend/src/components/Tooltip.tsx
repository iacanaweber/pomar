import { useState, useRef, useEffect } from "react";
import { useGlossary } from "../hooks/useGlossary";

/**
 * Tooltip explicativo. Funciona por hover (desktop) e por toque (mobile).
 * Recebe `metricKey` para resolver a explicação no glossário do backend.
 */
export function Tooltip({ metricKey, children }: { metricKey: string; children: React.ReactNode }) {
  const glossary = useGlossary();
  const entry = glossary[metricKey];
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("click", onDoc);
    return () => document.removeEventListener("click", onDoc);
  }, [open]);

  if (!entry) return <>{children}</>;

  return (
    <span
      className="tip"
      ref={ref}
      // Só o ponteiro FINO abre por hover. Com `onMouseEnter`, um toque disparava o
      // mouseenter sintético (abre) e logo em seguida o click (fecha): no celular o
      // tooltip abria e sumia no mesmo gesto, e a explicação era inalcançável.
      onPointerEnter={(e) => e.pointerType === "mouse" && setOpen(true)}
      onPointerLeave={(e) => e.pointerType === "mouse" && setOpen(false)}
    >
      <span
        className="tip-anchor"
        role="button"
        tabIndex={0}
        aria-expanded={open}
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            setOpen((v) => !v);
          }
          if (e.key === "Escape") setOpen(false);
        }}
      >
        {children}
        <span className="tip-mark">ⓘ</span>
      </span>
      {open && (
        <span className="tip-box" role="tooltip">
          <strong>{entry.label}</strong>
          <span className="tip-def">{entry.definition}</span>
          <span className="tip-meta">
            <em>Como ler:</em> {entry.interpretation}
          </span>
          <span className="tip-src">Fonte: {entry.source}</span>
        </span>
      )}
    </span>
  );
}
