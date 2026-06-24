import { useEffect, useState } from "react";

/**
 * Micro-feedback "✓ salvo". Controlado por uma chave que muda a cada salvamento
 * (ex.: o timestamp do onSuccess). Some sozinho após `duration` ms.
 */
export function SavedToast({
  show,
  message = "✓ Preferências salvas",
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
      {message}
    </div>
  );
}
