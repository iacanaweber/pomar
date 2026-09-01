import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ApiError } from "../../api/client";
import { MutationError } from "../../components/MutationError";
import { useAssignments, useFixedIncome, useUpdateAccount } from "../../api/queries";
import { money, pct } from "../../lib/format";
import { Tooltip } from "../../components/Tooltip";
import { Icon } from "../../components/Icon";
import { AccountCard } from "./AccountCard";
import { NewAccountForm } from "./NewAccountForm";
import { ReserveFloorCard } from "./ReserveFloorCard";

/** Chave do aviso único de "marque o que conta na carteira".
 *
 *  Com guarda, como `useTheme` já fazia com a mesma API: em contexto onde o
 *  armazenamento lança (modo privado, cota estourada), a leitura acontecia dentro de um
 *  inicializador de `useState` e derrubava a página inteira no ErrorBoundary — por causa
 *  de um aviso dispensável. */
const AVISO_MARCAR = "pomar:reserva-aviso-marcar";

const leuAviso = (): boolean => {
  try {
    return !!localStorage.getItem(AVISO_MARCAR);
  } catch {
    return false;
  }
};

const marcarAvisoLido = () => {
  try {
    localStorage.setItem(AVISO_MARCAR, "1");
  } catch {
    // Sem armazenamento o aviso reaparece na próxima visita. É o pior caso aceitável.
  }
};

export function ReservePage() {
  const navigate = useNavigate();
  // Atalho do Plantar (/reserva?conta=7): abre a conta sugerida já no lançamento, para o
  // usuário não ter que reencontrá-la e redigitar o que o plano acabou de dizer.
  const [params] = useSearchParams();
  const contaDoAtalho = Number(params.get("conta")) || null;
  const { data, isLoading, error } = useFixedIncome();
  const update = useUpdateAccount();
  const tags = useAssignments({ dimension: "indexer", subjectType: "fi_account" });
  const [showArchived, setShowArchived] = useState(false);
  const [avisoLido, setAvisoLido] = useState(leuAviso);

  const accounts = (data?.accounts ?? []).filter((a) => !a.archived);
  const archived = (data?.accounts ?? []).filter((a) => a.archived);
  const tagOf = new Map((tags.data ?? []).map((t) => [t.subject_id, t]));
  // Contas antigas nasceram fora da carteira (default deliberado): um aviso de uma linha,
  // dispensável, em vez de mudar o comportamento delas por conta própria.
  const precisaMarcar = accounts.length > 0 && accounts.every((a) => !a.counts_in_portfolio);

  return (
    <main className="page">
      <button className="link-button" onClick={() => navigate(-1)}>
        ← voltar
      </button>
      <h1 className="page-title">Renda fixa</h1>

      {isLoading && (
        <p className="muted" role="status">
          Carregando
        </p>
      )}
      {error && (
        <div className="banner banner-error">
          <Icon name="alert" size={15} />{" "}
          {error instanceof ApiError ? error.userMessage : "Erro ao ler a renda fixa."}
        </div>
      )}

      {data && (
        <div className="pf-summary">
          <span className="muted">Total em renda fixa</span>
          <strong className="pf-total">{money(data.total_balance)}</strong>
          <div className="reserve-totals">
            <span>
              Conta na carteira <strong>{money(data.portfolio_balance)}</strong>
            </span>
            <span>
              <Tooltip metricKey="liquid_reserve">
                <span>Reserva líquida</span>
              </Tooltip>{" "}
              <strong>{money(data.liquid_balance)}</strong>
            </span>
            {data.excluded_unmarked > 0 && (
              <span>
                Não marcado <strong>{money(data.excluded_unmarked)}</strong>
              </span>
            )}
            {data.excluded_earmarked > 0 && (
              <span>
                Reservado p/ outro fim <strong>{money(data.excluded_earmarked)}</strong>
              </span>
            )}
            {data.total_gain !== 0 && (
              <span>
                Rendimento acumulado <strong>{money(data.total_gain)}</strong>
              </span>
            )}
          </div>
          {data.cdi_annual != null && (
            <span className="muted">CDI de referência: {pct(data.cdi_annual)} a.a.</span>
          )}
        </div>
      )}

      {data && <ReserveFloorCard floor={data.floor} />}

      {data && accounts.length === 0 && (
        <div className="banner banner-warn">
          Nenhuma aplicação. Adicione conta, CDB ou Tesouro para acompanhar o rendimento.
        </div>
      )}

      {precisaMarcar && !avisoLido && (
        <p className="banner radar-banner">
          Marque em cada conta se ela conta no patrimônio.{" "}
          <button
            className="link-button"
            onClick={() => {
              marcarAvisoLido();
              setAvisoLido(true);
            }}
          >
            ok, entendi
          </button>
        </p>
      )}

      {accounts.length > 0 && (
        <ul className="cards">
          {accounts.map((a) => (
            <AccountCard
              key={a.id}
              account={a}
              tag={tagOf.get(String(a.id))}
              autoOpen={a.id === contaDoAtalho}
            />
          ))}
        </ul>
      )}

      <NewAccountForm />

      {archived.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <button className="link-button" onClick={() => setShowArchived((v) => !v)}>
            <>
              <Icon name="chevron" size={14} />{" "}
              {showArchived ? "Ocultar arquivadas" : `Arquivadas (${archived.length})`}
            </>
          </button>
          {showArchived && (
            <ul className="cards" style={{ marginTop: 8 }}>
              {archived.map((a) => (
                <li key={a.id} className="card reserve-archived-row">
                  <div className="reserve-card-head">
                    <div className="card-id">
                      <span className="card-ticker">{a.name}</span>
                      <span className="card-name">
                        arquivada · último saldo {money(a.current_balance)}
                      </span>
                    </div>
                    <button
                      className="link-button"
                      disabled={update.isPending}
                      onClick={() => update.mutate({ id: a.id, body: { archived: false } })}
                    >
                      Desarquivar
                    </button>
                  </div>
                  <MutationError error={update.error} acao={`desarquivar ${a.name}`} />
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <p className="disclaimer">Rendimento calculado a partir dos saldos informados.</p>
    </main>
  );
}
