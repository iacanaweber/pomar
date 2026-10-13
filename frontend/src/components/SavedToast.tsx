import { useEffect, useState } from "react";
import { Icon } from "./Icon";

/**
 * Micro-feedback de "salvo", com o ícone de confirmação. Controlado por uma chave que muda a cada salvamento
 * (ex.: o timestamp do onSuccess). Some sozinho após `duration` ms.
 */
export function SavedToast({
  show,
  message = "Preferências salvas.",
  duration = 2000,
}: {
  show: number | null;
  message?: string;
  duration?: number;
}) {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    if (show == null) return;
    setVisible(true);
    const t = setTimeout(() => setVisible(false), duration);
    return () => clearTimeout(t);
  }, [show, duration]);

  if (!visible) return null;
  return (
    <div className="saved-toast" role="status" aria-live="polite">
      <Icon name="check" size={16} className="icon-inline" /> {message}
    </div>
  );
}
