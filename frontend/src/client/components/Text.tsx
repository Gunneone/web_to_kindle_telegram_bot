import type { ReactNode } from 'react';

const SEPARATORS = /(\s\/\s|·|=)/;

/** `// web → kindle · dortmund` with the separators picked out in orange. */
export function Eyebrow({ children }: { children: string }) {
  const parts = children.split(SEPARATORS);
  return (
    <div className="g1-eyebrow">
      {parts.map((part, index) =>
        index % 2 === 1 ? (
          <span key={index} className="g1-hl">
            {part}
          </span>
        ) : (
          part
        ),
      )}
    </div>
  );
}

/** A joke in the margin: handwritten, orange, never on anything functional. */
export function Scribble({ children }: { children: ReactNode }) {
  return <span className="g1-scribble">{children}</span>;
}

export function PageHead({
  eyebrow,
  title,
  scribble,
  lead,
}: {
  eyebrow: string;
  title: string;
  scribble?: string;
  lead?: ReactNode;
}) {
  return (
    <header className="g1-page-head">
      <Eyebrow>{eyebrow}</Eyebrow>
      <h1 className="g1-title">
        {title}
        {scribble && (
          <>
            {' '}
            <Scribble>{scribble}</Scribble>
          </>
        )}
      </h1>
      {lead && <p className="g1-lead">{lead}</p>}
    </header>
  );
}

export function SectionHead({ eyebrow, title, action }: { eyebrow: string; title: string; action?: ReactNode }) {
  return (
    <div className="g1-section-head">
      <div>
        <Eyebrow>{eyebrow}</Eyebrow>
        <h2>{title}</h2>
      </div>
      {action}
    </div>
  );
}
