import { useEffect, useRef, useState } from "react";

import type { Comparison } from "../lib/comparison";
import { AT_TARGET_PP } from "../lib/comparison";
import { CLASS_LABEL } from "../lib/classes";
import { money, pctPts, signedPp } from "../lib/format";
import { byClassOrder, classHue } from "../lib/viz";

/** O canteiro: a carteira ALVO é o leito, o que você tem preenche cada cova.
 *
 *  A tese da tela em um objeto. A largura de cada cova é o peso alvo da classe — o
 *  desenho que o usuário escolheu em /alvo — e a altura preenchida é quanto dele já
 *  existe. Vazio é onde plantar, e é a única leitura que o próximo aporte precisa.
 *
 *  Substitui três componentes que respondiam pedaços desta mesma pergunta em telas
 *  diferentes (AllocationSummary em Plantar, StackedBar dentro de PortfolioVsTarget na
 *  Carteira, TargetPortfolioChart em /alvo) e que duplicavam CLASS_HUE e a rampa de cor.
 *
 *  Lógica nova: nenhuma. `buildComparison()` já devolve exatamente isto — e tem 316
 *  linhas de teste. Aqui só se desenha. */

/** Piso de largura: uma classe de 3% ainda precisa ser tocável (44px é o alvo auditado
 *  no app inteiro). Sem isto, o alvo de renda fixa de um usuário conservador some. */
const LARGURA_MIN = 44;

/** Altura do leito. Alta o bastante para o preenchimento ser legível de relance, baixa o
 *  bastante para caber acima da dobra junto com o formulário de aporte. */
const ALTURA = 84;

interface Props {
  comparison: Comparison;
  /** Quanto o plano recém-gerado adiciona a cada classe, em R$. Entra como camada clara
   *  em cima do preenchimento atual: "onde isto vai cair". */
  aporte?: Record<string, number>;
  /** Fração do gap que o legado cobriria (0..1+), quando o plano calculou. Aritmética,
   *  NÃO sugestão de venda — o app não recomenda vender nada. É só a conta que o usuário
   *  não faz de cabeça. */
  coberturaLegado?: number | null;
  gapLegado?: number | null;
  moeda?: string;
}

export function Canteiro({
  comparison,
  aporte,
  coberturaLegado,
  gapLegado,
  moeda = "BRL",
}: Props) {
  const { byClass, legacy, legacyValue, legacyPct, targetBase, hasTarget } = comparison;

  if (!hasTarget || byClass.length === 0) {
    return (
      <div className="canteiro-vazio card">
        <h3>Sem carteira alvo</h3>
        <p className="muted">
          O canteiro desenha as metas por classe. Defina-as e o Plantar passa a dizer onde
          aportar.
        </p>
      </div>
    );
  }

  const covas = [...byClass]
    .filter((c) => c.targetPct > 0 || c.currentValue > 0)
    .sort((a, b) => byClassOrder(a.cls, b.cls));

  return (
    <section className="canteiro">
      <Leito covas={covas} aporte={aporte} targetBase={targetBase} moeda={moeda} />
      <Tabela covas={covas} moeda={moeda} />
      {legacyValue > 0 && (
        <ForaDoCanteiro
          valor={legacyValue}
          pct={legacyPct}
          tickers={legacy.map((r) => r.ticker)}
          cobertura={coberturaLegado}
          gap={gapLegado}
          moeda={moeda}
        />
      )}
    </section>
  );
}

function Leito({
  covas,
  aporte,
  targetBase,
  moeda,
}: {
  covas: Comparison["byClass"];
  aporte?: Record<string, number>;
  targetBase: number;
  moeda: string;
}) {
  // Uma única animação de entrada, e só ela: as covas crescem do chão. `prefers-reduced-
  // motion` é respeitado no CSS, e aqui o estado começa já preenchido quando o usuário
  // pediu menos movimento — senão a barra ficaria em zero para sempre.
  const [entrou, setEntrou] = useState(() =>
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches,
  );
  const jaAnimou = useRef(false);
  useEffect(() => {
    if (jaAnimou.current) return;
    jaAnimou.current = true;
    const id = requestAnimationFrame(() => setEntrou(true));
    return () => cancelAnimationFrame(id);
  }, []);

  const resumo = covas
    .map((c) => `${CLASS_LABEL[c.cls] ?? c.cls} ${pctPts(c.currentPct)} de ${pctPts(c.targetPct)}`)
    .join("; ");

  return (
    <div
      className="canteiro-leito"
      style={{ height: ALTURA }}
      role="img"
      aria-label={`Carteira atual contra o alvo, por classe: ${resumo}.`}
    >
      {covas.map((c, i) => {
        const alvoBrl = (c.targetPct / 100) * targetBase;
        // Preenchimento é limitado a 100%: acima do alvo NÃO é uma cova mais que cheia,
        // é uma marca acima da borda. Barra de 130% não quer dizer nada.
        const razao = alvoBrl > 0 ? c.currentValue / alvoBrl : c.currentValue > 0 ? 1 : 0;
        const preenchido = Math.min(razao, 1) * 100;
        const excedeu = razao > 1 + AT_TARGET_PP / 100;

        const somaBrl = aporte?.[c.cls] ?? 0;
        const somaPct =
          alvoBrl > 0 ? Math.min(somaBrl / alvoBrl, 1 - preenchido / 100) * 100 : 0;

        return (
          <div
            className="canteiro-cova"
            key={c.cls}
            style={{
              // A largura é o peso ALVO: o leito É o desenho da carteira.
              flexGrow: Math.max(c.targetPct, 0.5),
              minWidth: LARGURA_MIN,
            }}
          >
            <div className="canteiro-terra">
              {excedeu && <span className="canteiro-excesso" aria-hidden="true" />}
              <div
                className="canteiro-cheio"
                style={{
                  height: entrou ? `${preenchido}%` : 0,
                  background: classHue(c.cls),
                  transitionDelay: `${i * 40}ms`,
                }}
              />
              {somaPct > 0 && (
                <div
                  className="canteiro-aporte"
                  style={{
                    bottom: `${preenchido}%`,
                    height: entrou ? `${somaPct}%` : 0,
                    background: classHue(c.cls),
                    transitionDelay: `${i * 40}ms`,
                  }}
                  title={`o aporte adiciona ${money(somaBrl, moeda)}`}
                />
              )}
            </div>
            <span className="canteiro-nome">{CLASS_LABEL[c.cls] ?? c.cls}</span>
          </div>
        );
      })}
    </div>
  );
}

/** A legenda É a tabela. Duas coisas de uma vez: o detalhe numérico que o leito resume, e
 *  a semântica que um `<ul>` de grid nunca deu a quem usa leitor de tela. */
function Tabela({ covas, moeda }: { covas: Comparison["byClass"]; moeda: string }) {
  return (
    <div className="canteiro-tabela-wrap">
      <table className="canteiro-tabela">
        <caption className="sr-only">Carteira atual contra o alvo, por classe</caption>
        <thead>
          <tr>
            <th scope="col">Classe</th>
            <th scope="col">Hoje</th>
            <th scope="col">Alvo</th>
            <th scope="col">Desvio</th>
            <th scope="col">Falta</th>
          </tr>
        </thead>
        <tbody>
          {covas.map((c) => {
            const noAlvo = Math.abs(c.deltaPp) < AT_TARGET_PP;
            return (
              <tr key={c.cls}>
                <th scope="row">
                  <span className="canteiro-marca" style={{ background: classHue(c.cls) }} />
                  {CLASS_LABEL[c.cls] ?? c.cls}
                </th>
                <td>{pctPts(c.currentPct)}</td>
                <td className="muted">{pctPts(c.targetPct)}</td>
                <td>{noAlvo ? <span className="muted">no alvo</span> : signedPp(c.deltaPp)}</td>
                <td>
                  {noAlvo ? (
                    <span className="muted">—</span>
                  ) : c.deltaPp > 0 ? (
                    /* Quente = agir. É a única cor alta da interface, e ela só aparece
                       onde dinheiro deve ir. */
                    <span className="canteiro-plantar">{money(c.deltaBrl, moeda)}</span>
                  ) : (
                    <span className="canteiro-sobra">
                      sobra {money(Math.abs(c.deltaBrl), moeda)}
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/** O legado fica literalmente FORA do leito — que é o que ele é: capital sem alvo contra
 *  o qual medir. Não é sugestão de venda; é a aritmética que o usuário não faz de cabeça. */
function ForaDoCanteiro({
  valor,
  pct,
  tickers,
  cobertura,
  gap,
  moeda,
}: {
  valor: number;
  pct: number;
  tickers: string[];
  cobertura?: number | null;
  gap?: number | null;
  moeda: string;
}) {
  return (
    <p className="canteiro-fora">
      <strong>{money(valor, moeda)}</strong> fora do canteiro ({pctPts(pct)} do patrimônio)
      {tickers.length > 0 && (
        <>
          {" — "}
          {tickers.slice(0, 4).join(", ")}
          {tickers.length > 4 ? ` e mais ${tickers.length - 4}` : ""}
        </>
      )}
      . Sem alvo definido, não entra na conta de desvio.
      {cobertura != null && gap != null && gap > 0 && (
        <>
          {" "}
          Vender tudo cobriria <strong>{pctPts(Math.min(cobertura, 1) * 100, 0)}</strong> do
          que falta ({money(gap, moeda)}){cobertura > 1 && ", com sobra"}.
        </>
      )}
    </p>
  );
}
