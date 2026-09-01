import { useState, useRef, useEffect, useId } from "react";
import { useGlossary } from "../hooks/useGlossary";
import { Icon } from "./Icon";

/**
 * Tooltip explicativo. Funciona por hover (desktop) e por toque (mobile).
 * Recebe `metricKey` para resolver a explicação no glossário do backend.
 *
 * O GATILHO é o ícone, não o valor. Antes o `role="button" tabIndex={0}` envolvia
 * `children` — e como este componente embrulha CIFRAS (YoC, DY, patrimônio, desvio),
 * cada número da tela virava uma parada de tabulação anunciada como botão. Percorrer a
 * Carteira pelo teclado era passar por dezenas de "botões" que só abriam glossário.
 *
 * E a caixa (`role="tooltip"`) nunca era ligada ao gatilho: quem usa leitor de tela
 * ativava e não ouvia nada de novo. Agora ela tem id e entra por `aria-describedby`.
 */
export function Tooltip({ metricKey, children }: { metricKey: string; children: React.ReactNode }) {
  const glossary = useGlossary();
  const entry = glossary[metricKey];
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);
  const id = useId();

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
      onKeyDown={(e) => {
        if (e.key === "Escape") setOpen(false);
      }}
    >
      <span className="tip-anchor">{children}</span>
      <button
        type="button"
        className="tip-trigger"
        aria-label={`O que é ${entry.label}`}
        aria-expanded={open}
        aria-describedby={open ? id : undefined}
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
      >
        <Icon name="info" size={14} className="icon icon-info tip-mark" />
      </button>
      {open && (
        <span className="tip-box" role="tooltip" id={id}>
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
