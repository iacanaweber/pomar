import { useHealth } from "../api/queries";

/** Aviso de saúde das fontes: avisa quando Ghostfolio/brapi não respondem, com orientação acionável. */
export function HealthBanner() {
  const { data } = useHealth();
  if (!data || (data.ghostfolio && data.brapi)) return null;
  return (
    <div className="banner banner-warn">
      {!data.ghostfolio && (
        <div>
          <strong>Ghostfolio desconectado.</strong> Confira <code>GHOSTFOLIO_URL</code> e o
          token. O plano segue com carteira vazia, mirando as metas.
        </div>
      )}
      {!data.brapi && (
        <div>
          <strong>brapi indisponível.</strong> Confira <code>BRAPI_TOKEN</code>.
        </div>
      )}
    </div>
  );
}
