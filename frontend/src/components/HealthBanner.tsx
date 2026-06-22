import { useHealth } from "../api/queries";

/** Onboarding leve: avisa quando Ghostfolio/brapi não respondem, com orientação acionável. */
export function HealthBanner() {
  const { data } = useHealth();
  if (!data || (data.ghostfolio && data.brapi)) return null;
  return (
    <div className="banner banner-warn">
      {!data.ghostfolio && (
        <div>
          • <strong>Ghostfolio não conectado.</strong> Confira <code>GHOSTFOLIO_URL</code> e o token
          (Settings → Security Token). O plano segue com carteira vazia mirando suas metas.
        </div>
      )}
      {!data.brapi && (
        <div>
          • <strong>brapi indisponível.</strong> Dados de mercado podem faltar — confira{" "}
          <code>BRAPI_TOKEN</code>.
        </div>
      )}
    </div>
  );
}
