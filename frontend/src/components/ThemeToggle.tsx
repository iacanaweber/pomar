import { useTheme } from "../hooks/useTheme";
import { Icon } from "./Icon";

/** Alterna claro/escuro. Cor nunca sozinha: traz ícone + rótulo acessível. */
export function ThemeToggle() {
  const { theme, toggle } = useTheme();
  const dark = theme === "dark";
  return (
    <button
      className="header-action theme-toggle"
      onClick={toggle}
      aria-label={dark ? "Mudar para tema claro" : "Mudar para tema escuro"}
      title={dark ? "Tema claro" : "Tema escuro"}
    >
      <Icon name={dark ? "sun" : "moon"} size={18} />
    </button>
  );
}
