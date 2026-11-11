import { Fragment, type ReactNode } from 'react';
import { Link } from 'react-router';
import { useT } from '../i18n';
import type { en } from '../i18n/en';

/** The questions there are answers for, in `faq.items` of the translations. */
export type Question = keyof typeof en.faq.items;

/** `notArriving` → `not-arriving`: the anchor that links straight to a question, as in `/faq#not-arriving`. */
export const anchorOf = (question: Question) => question.replace(/[A-Z]/g, (letter) => `-${letter.toLowerCase()}`);

const LINK = /\[([^\]]+)\]\(([^)\s]+)\)/g;

/** Text with `[label](/path)` or `[label](https://…)` links in it, as in the FAQ answers. */
export function RichText({ text }: { text: string }) {
  const parts: ReactNode[] = [];
  let last = 0;
  for (const match of text.matchAll(LINK)) {
    const [whole, label, href] = match;
    parts.push(text.slice(last, match.index));
    parts.push(
      href.startsWith('/') ? (
        <Link key={match.index} className="g1-link" to={href}>
          {label}
        </Link>
      ) : (
        <a key={match.index} className="g1-link" href={href} target="_blank" rel="noopener noreferrer">
          {label}
        </a>
      ),
    );
    last = match.index + whole.length;
  }
  parts.push(text.slice(last));
  return parts.map((part, index) => <Fragment key={index}>{part}</Fragment>);
}

/** A list of questions that each open to their answer. */
export function FaqList({ questions }: { questions: readonly Question[] }) {
  const t = useT();
  return (
    <div className="border-t border-line">
      {questions.map((question) => (
        <details key={question} id={anchorOf(question)} className="esel-faq border-b border-line">
          <summary>{t(`faq.items.${question}.q`)}</summary>
          <p className="m-0 max-w-prose pb-4 text-muted">
            <RichText text={t(`faq.items.${question}.a`)} />
          </p>
        </details>
      ))}
    </div>
  );
}
