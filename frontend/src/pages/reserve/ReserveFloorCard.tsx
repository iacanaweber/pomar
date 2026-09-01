import { useState } from "react";
import { MutationError } from "../../components/MutationError";
import { usePreferences, useSavePreferences } from "../../api/queries";
import type { FloorStatus } from "../../types";
import { brToISO, isoToBR, money, parseBRL, todayBR } from "../../lib/format";
import { Tooltip } from "../../components/Tooltip";

/** Piso da reserva: o mínimo que fica em renda fixa de RESGATE IMEDIATO.
 *
 *  Não é uma reserva separada da carteira — é um piso dentro da própria classe de renda
 *  fixa, então o mesmo dinheiro nunca aparece duas vezes no patrimônio. Aplicação travada
 *  soma no peso da classe e não conta aqui: o piso mede o que está disponível hoje.
 */
export function ReserveFloorCard({ floor }: { floor: FloorStatus | null | undefined }) {
  const prefs = usePreferences();
  const savePrefs = useSavePreferences();
  const [editing, setEditing] = useState(false);
  const [amount, setAmount] = useState("");
  const [index, setIndex] = useState<"none" | "ipca">("none");
  const [date, setDate] = useState(todayBR());

  const dateInvalid = date.trim() !== "" && brToISO(date) === null;

  const open = () => {
    const saved = prefs.data;
    setAmount(
      saved?.reserve_floor_amount ? String(saved.reserve_floor_amount).replace(".", ",") : "",
    );
    setIndex(saved?.reserve_floor_index ?? "none");
    setDate(saved?.reserve_floor_date ? isoToBR(saved.reserve_floor_date) : todayBR());
    setEditing(true);
  };

  const save = () => {
    const value = parseBRL(amount);
    if (!(value >= 0) || dateInvalid) return;
    savePrefs.mutate(
      {
        reserve_floor_amount: value,
        reserve_floor_index: index,
        reserve_floor_date: index === "ipca" ? brToISO(date) : null,
      },
      { onSuccess: () => setEditing(false) },
    );
  };

  if (editing) {
    return (
      <form
        className="controls reserve-goal"
        onSubmit={(e) => {
          e.preventDefault();
          save();
        }}
      >
        <label className="field">
          <span>Piso da reserva (R$)</span>
          <div className="money">
            <span>R$</span>
            <input
              inputMode="decimal"
              placeholder="ex.: 30.000,00"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              autoFocus
            />
          </div>
        </label>
        <div className="adv-row">
          <label className="field">
            <span>Correção</span>
            <select value={index} onChange={(e) => setIndex(e.target.value as "none" | "ipca")}>
              <option value="none">Nenhuma (valor nominal)</option>
              <option value="ipca">IPCA a partir da data-base</option>
            </select>
          </label>
          {index === "ipca" && (
            <label className="field">
              <span>Data-base</span>
              <input
                inputMode="numeric"
                placeholder="dd/mm/aaaa"
                maxLength={10}
                value={date}
                onChange={(e) => setDate(e.target.value)}
              />
              {dateInvalid && <span className="field-error">Use o formato dd/mm/aaaa.</span>}
            </label>
          )}
        </div>
        <div className="reserve-actions">
          <button className="primary" type="submit" disabled={savePrefs.isPending || dateInvalid}>
            {savePrefs.isPending ? "Salvando" : "Salvar piso"}
          </button>
          <MutationError error={savePrefs.error} acao="salvar o piso da reserva" />
          <button className="link-button" type="button" onClick={() => setEditing(false)}>
            Cancelar
          </button>
        </div>
      </form>
    );
  }

  if (!floor || floor.floor_nominal <= 0) {
    return (
      <div className="alloc reserve-goal">
        <p className="muted" style={{ margin: 0 }}>
          Sem piso definido. Nenhum aporte é desviado para a renda fixa.
        </p>
        <button className="link-button" onClick={open}>
          Definir piso da reserva
        </button>
      </div>
    );
  }

  const filled = Math.round(floor.pct_filled * 100);
  const corrigido = floor.index === "ipca" && floor.index_available;

  return (
    <div className={`alloc reserve-goal ${floor.deficit > 0 ? "" : "goal-met"}`}>
      <div className="goal-head">
        <h3 style={{ margin: 0 }}>
          <Tooltip metricKey="reserve_floor">
            <span>Piso da reserva</span>
          </Tooltip>
        </h3>
        <button className="link-button" onClick={open}>
          editar
        </button>
      </div>
      <div
        className="goal-bar"
        role="progressbar"
        aria-valuenow={filled}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Reserva líquida: ${filled}% do piso`}
      >
        <div className="alloc-track" style={{ height: 18 }}>
          {/* A cor sai do CSS (.goal-met), não de um style inline. */}
          <div className="alloc-cur" style={{ width: `${Math.min(100, filled)}%` }} />
        </div>
        <span className="goal-bar-label">{filled}% do piso</span>
      </div>
      <p className="goal-status" style={{ marginBottom: 0 }}>
        Piso <strong>{money(floor.floor_corrected)}</strong> · reserva líquida{" "}
        <strong>{money(floor.liquid_reserve)}</strong>
        {floor.deficit > 0 ? (
          <>
            {" "}
            · faltam <strong>{money(floor.deficit)}</strong>
          </>
        ) : (
          <> · cumprido</>
        )}
      </p>
      {corrigido && (
        <p className="muted" style={{ fontSize: 12, margin: 0 }}>
          Nominal {money(floor.floor_nominal)}, corrigido pelo IPCA desde{" "}
          {floor.floor_date ? isoToBR(floor.floor_date) : "—"}.
        </p>
      )}
      {floor.index === "ipca" && !floor.index_available && (
        <p className="muted" style={{ fontSize: 12, margin: 0 }}>
          IPCA indisponível. Exibindo o piso nominal.
        </p>
      )}
      <p className="muted" style={{ fontSize: 12, margin: 0 }}>
        Só resgate imediato, e só o que conta na carteira.
      </p>
    </div>
  );
}
