import type { ReactNode } from "react";
import { Link } from "react-router-dom";

/** Link para a página de detalhe do ativo (/ativo/:ticker). */
export function AssetLink({ ticker, children }: { ticker: string; children?: ReactNode }) {
  return (
    <Link to={`/ativo/${ticker}`} className="asset-link" onClick={(e) => e.stopPropagation()}>
      {children ?? ticker}
    </Link>
  );
}
