/** Esqueleto de carregamento no FORMATO da tela que vem.
 *
 *  O "Carregando" em texto deixava a tela vazia e, quando os dados chegavam, tudo pulava
 *  de lugar de uma vez. Os blocos ocupam o espaço dos cartões reais (mesma superfície,
 *  mesmo raio), então a chegada dos dados troca o conteúdo sem mexer no layout.
 *  Para leitor de tela continua sendo um status com texto.
 */
export type SkeletonBlock = "title" | "line" | "sm" | "md" | "lg";

export function Skeleton({
  blocks,
  label = "Carregando",
}: {
  blocks: SkeletonBlock[];
  label?: string;
}) {
  return (
    <div className="skeleton" role="status" aria-busy="true">
      <span className="sr-only">{label}</span>
      {blocks.map((b, i) => (
        <div key={i} className={`skeleton-block skeleton-${b}`} aria-hidden="true" />
      ))}
    </div>
  );
}

/** Página inteira: título e três cartões. Serve a qualquer tela enquanto o chunk carrega. */
export function PageSkeleton({ label }: { label?: string }) {
  return (
    <main className="page">
      <Skeleton blocks={["title", "md", "lg", "md"]} label={label} />
    </main>
  );
}
