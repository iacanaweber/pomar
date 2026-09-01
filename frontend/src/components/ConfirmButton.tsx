import { useEffect, useRef, useState } from "react";

import { Icon, type IconName } from "./Icon";

/** Ação destrutiva com confirmação EM LINHA, no lugar de `confirm()`.
 *
 *  O `confirm()` nativo bloqueia a thread, não é estilizável nem testável, e em modo
 *  standalone aparece com o nome do host no título — a caixa do sistema operacional
 *  irrompendo no meio de um app instalado. Havia ainda duas convenções para a mesma
 *  coisa no código: `confirm(...)` numa tela e `window.confirm(...)` na outra.
 *
 *  Aqui o botão vira a própria pergunta: um toque arma, o segundo executa, e qualquer
 *  outra coisa (Escape, clique fora, cinco segundos) desarma. A ação destrutiva continua
 *  exigindo dois gestos deliberados, sem sequestrar a tela. */
export function ConfirmButton({
  onConfirm,
  pergunta,
  rotulo,
  icone,
  disabled,
  className = "link-button",
}: {
  onConfirm: () => void;
  /** O que aparece quando armado. Curto e no imperativo: "Remover mesmo?" */
  pergunta: string;
  /** Descrição da ação para leitor de tela — o botão em repouso costuma ser só ícone. */
  rotulo: string;
  icone?: IconName;
  disabled?: boolean;
  className?: string;
}) {
  const [armado, setArmado] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!armado) return;
    // Desarma sozinho: um botão que fica armado indefinidamente vira armadilha para o
    // próximo toque distraído.
    const t = setTimeout(() => setArmado(false), 5000);
    const foraDaCaixa = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setArmado(false);
    };
    document.addEventListener("click", foraDaCaixa);
    return () => {
      clearTimeout(t);
      document.removeEventListener("click", foraDaCaixa);
    };
  }, [armado]);

  if (armado) {
    return (
      <span className="confirm" ref={ref} onKeyDown={(e) => e.key === "Escape" && setArmado(false)}>
        <span className="confirm-pergunta">{pergunta}</span>
        <button
          type="button"
          className="confirm-sim"
          disabled={disabled}
          onClick={(e) => {
            e.stopPropagation();
            setArmado(false);
            onConfirm();
          }}
        >
          Confirmar
        </button>
        <button type="button" className="link-button" onClick={() => setArmado(false)}>
          Cancelar
        </button>
      </span>
    );
  }

  return (
    <button
      type="button"
      className={className}
      disabled={disabled}
      aria-label={rotulo}
      onClick={(e) => {
        e.stopPropagation();
        setArmado(true);
      }}
    >
      {icone ? <Icon name={icone} size={18} /> : rotulo}
    </button>
  );
}
