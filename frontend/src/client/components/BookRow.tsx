import { useMutation } from '@tanstack/react-query';
import { IconArrowUpRight, IconDownload, IconRefresh, IconSend, IconTrash } from '@tabler/icons-react';
import { useState } from 'react';
import { Link, useLocation } from 'react-router';
import { useI18n, type MessageKey } from '../i18n';
import { deleteBook, downloadUrl, errorCode, type Book, type Stage, type Target } from '../lib/api';
import { placeOf, useArrivalHint, useRefreshBooks, type Place } from '../lib/books';
import { formatDate, formatSize } from '../lib/format';
import { useMe } from '../lib/session';
import { ErrorCallout } from './Callout';

const STEP_OF_STAGE: Record<Stage, number> = { received: -1, queued: -1, fetching: 0, building: 1, sending: 2 };

/** Fetch → build → deliver (or preview, when the book is only being made), with the current step marked. */
export function ProgressStrip({ stage, last = 'deliver' }: { stage: Stage | null; last?: 'deliver' | 'preview' }) {
  const { t } = useI18n();
  const current = stage ? STEP_OF_STAGE[stage] : -1;
  const steps = ['fetch', 'build', last] as const;
  return (
    <div className="mt-3">
      <ol className="m-0 flex list-none gap-2 p-0" aria-label={t('books.progress')}>
        {steps.map((step, index) => (
          <li
            key={step}
            aria-current={index === current ? 'step' : undefined}
            className={`flex-1 border-t-2 pt-1 font-mono text-xs uppercase tracking-wider ${
              index < current
                ? 'border-primary text-muted'
                : index === current
                  ? 'border-accent text-fg'
                  : 'border-line text-subtle'
            }`}
          >
            {t(`books.steps.${step}`)}
          </li>
        ))}
      </ol>
      <p className="g1-meta mb-0 mt-2" aria-live="polite">
        {t(`books.stage.${stage ?? 'received'}`)}
      </p>
    </div>
  );
}

const BADGE: Record<Place, string> = {
  processing: 'g1-badge g1-badge--soft',
  kindle: 'g1-badge g1-badge--primary',
  telegram: 'g1-badge g1-badge--primary',
  sent: 'g1-badge g1-badge--primary',
  ready: 'g1-badge',
  failed: 'g1-badge text-danger [--g1-edge:var(--g1-danger)]',
  interrupted: 'g1-badge text-warning [--g1-edge:var(--g1-warning)]',
};

/** Where the book went (or that it is still being made, or failed), and a separate tag when it is paywalled. */
export function BookBadges({ book }: { book: Book }) {
  const { t } = useI18n();
  const place = placeOf(book);
  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      <span className={BADGE[place]}>{t(`books.place.${place}`)}</span>
      {book.paywalled && place !== 'processing' && (
        <span className="g1-badge g1-badge--soft" title={t('books.previewNote')}>
          {t('books.paywalled')}
        </span>
      )}
    </span>
  );
}

export function failureText(book: Book, t: (key: MessageKey, vars?: Record<string, string>) => string): string {
  // Interrupted with the book already made: the restart came while it was being mailed
  if (book.status === 'interrupted') return t(book.can_download ? 'books.interruptedSending' : 'books.interrupted');
  const key = (book.failure ? `books.failure.${book.failure}` : 'books.failure.generic') as MessageKey;
  return t(key, { host: book.host });
}

/** Where a book link was followed from, so the book page can lead back there. */
export interface FromState {
  from?: string;
}

function useFrom(): FromState {
  const location = useLocation();
  return { from: location.pathname + location.search };
}

/** The book's title, opening it in Eselsohr. The page it came from is linked in the details line below (OriginalLink). */
export function BookTitle({ book, className = '' }: { book: Book; className?: string }) {
  const from = useFrom();
  return (
    <span className={`flex min-w-0 ${className}`}>
      <Link className="g1-link min-w-0 truncate font-medium" to={`/books/${book.id}`} state={from}>
        {book.title}
      </Link>
    </span>
  );
}

/** "en.wikipedia.org ↗" in a book's details line: the page the book came from, in a new tab. */
export function OriginalLink({ book }: { book: Book }) {
  const { t } = useI18n();
  return (
    <a
      className="inline-flex items-center gap-0.5 text-muted underline underline-offset-2 hover:text-fg"
      href={book.url}
      target="_blank"
      rel="noopener noreferrer"
      title={t('books.openOriginalOn', { host: book.host })}
    >
      {book.host}
      <IconArrowUpRight className="g1-icon" aria-hidden />
      <span className="g1-visually-hidden">{t('books.newTab')}</span>
    </a>
  );
}

/** "Not on your Kindle?", leading to the troubleshooting steps on the book page. */
export function NotArrivedLink({ book }: { book: Book }) {
  const { t } = useI18n();
  const from = useFrom();
  return (
    <Link className="g1-link text-sm" to={`/books/${book.id}#not-arrived`} state={from}>
      {t('books.notArrived')}
    </Link>
  );
}

/** "Delete this book?" with the buttons to do it or not. */
function DeleteConfirm({
  book,
  small,
  onCancel,
  onDeleted,
}: {
  book: Book;
  small: boolean;
  onCancel: () => void;
  onDeleted?: () => void;
}) {
  const { t } = useI18n();
  const refresh = useRefreshBooks();
  const remove = useMutation({
    mutationFn: () => deleteBook(book.id),
    onSuccess: () => {
      onDeleted?.();
      void refresh();
    },
  });
  const size = small ? ' g1-btn--sm' : '';
  return (
    <div className="flex flex-wrap items-center gap-2" role="group" aria-label={t('books.deleteLabel', { title: book.title })}>
      <span className="text-sm text-muted">{t('books.deleteConfirm')}</span>
      <span className="flex gap-2">
        <button
          type="button"
          className={`g1-btn${size} text-danger [--g1-edge:var(--g1-danger)]`}
          disabled={remove.isPending}
          autoFocus
          onClick={() => remove.mutate()}
        >
          {t('books.delete')}
        </button>
        <button type="button" className={`g1-btn g1-btn--ghost${size}`} onClick={onCancel}>
          {t('common.cancel')}
        </button>
      </span>
      {remove.isError && (
        <div className="basis-full">
          <ErrorCallout code={errorCode(remove.error)} />
        </div>
      )}
    </div>
  );
}

/**
 * "Send it again?" for a book that already went to the Kindle. Amazon never says whether a book arrived,
 * so a resend is the way out when one didn't, but if the first copy did arrive the book shows up twice.
 */
export function SendAgainConfirm({
  book,
  small,
  busy,
  onConfirm,
  onCancel,
}: {
  book: Book;
  small: boolean;
  busy: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const { t } = useI18n();
  const me = useMe();
  const size = small ? ' g1-btn--sm' : '';
  return (
    <div className="g1-stack max-w-prose" role="group" aria-label={t('books.sendAgainLabel', { title: book.title })}>
      <p className="m-0 text-sm">
        <strong className="block">{t('books.sendAgainTitle', { email: me?.kindle_email ?? '' })}</strong>
        <span className="text-muted">{t('books.sendAgainText')}</span>
      </p>
      <span className="flex flex-wrap gap-2">
        <button type="button" className={`g1-btn g1-btn--primary${size}`} disabled={busy} autoFocus onClick={onConfirm}>
          <IconSend className="g1-icon" aria-hidden />
          {t('books.sendAgainConfirm')}
        </button>
        <button type="button" className={`g1-btn g1-btn--ghost${size}`} onClick={onCancel}>
          {t('common.cancel')}
        </button>
      </span>
    </div>
  );
}

/** "Send again" (on the book page), asking first: the book may end up on the Kindle twice. */
export function SendAgain({ book, busy, onConfirm }: { book: Book; busy: boolean; onConfirm: () => void }) {
  const { t } = useI18n();
  const [confirming, setConfirming] = useState(false);
  if (confirming) {
    return (
      <SendAgainConfirm
        book={book}
        small={false}
        busy={busy}
        onCancel={() => setConfirming(false)}
        onConfirm={() => {
          setConfirming(false);
          onConfirm();
        }}
      />
    );
  }
  return (
    <button type="button" className="g1-btn" disabled={busy} onClick={() => setConfirming(true)}>
      <IconSend className="g1-icon" aria-hidden />
      {t('books.sendAgain')}
    </button>
  );
}

/** Delete one book (on its own page), after a second click to confirm. */
export function DeleteBook({ book, onDeleted }: { book: Book; onDeleted?: () => void }) {
  const { t } = useI18n();
  const [confirming, setConfirming] = useState(false);
  if (book.status === 'processing') return null;
  if (confirming) return <DeleteConfirm book={book} small={false} onCancel={() => setConfirming(false)} onDeleted={onDeleted} />;
  return (
    <button type="button" className="g1-btn g1-btn--ghost" onClick={() => setConfirming(true)}>
      <IconTrash className="g1-icon" aria-hidden />
      {t('books.delete')}
    </button>
  );
}

/** Download, send to Kindle, or try again: whatever makes sense for this book. */
export function BookActions({
  book,
  hasKindle,
  busy,
  onSend,
  deletable = false,
  nowrap = false,
}: {
  book: Book;
  hasKindle: boolean;
  busy: boolean;
  /** No target: make the book again without delivering it */
  onSend: (book: Book, target?: Target) => void;
  /** Offer to delete it (in the history) */
  deletable?: boolean;
  /** Keep the buttons on one line (in a table) */
  nowrap?: boolean;
}) {
  const { t } = useI18n();
  const [asking, setAsking] = useState<'delete' | 'resend' | null>(null);
  if (book.status === 'processing') return null;
  // A question ("delete?", "send again?") takes the place of the other actions, so they stay on one line otherwise
  if (asking === 'delete') return <DeleteConfirm book={book} small onCancel={() => setAsking(null)} />;
  if (asking === 'resend') {
    return (
      <SendAgainConfirm
        book={book}
        small
        busy={busy}
        onCancel={() => setAsking(null)}
        onConfirm={() => {
          setAsking(null);
          onSend(book, 'kindle');
        }}
      />
    );
  }
  const done = book.status === 'ready' || book.status === 'sent' || book.status === 'preview';
  // A failed or interrupted send leaves a finished book: send that again rather than making it anew
  const built = book.can_download;
  return (
    <div className={`flex items-center gap-2 ${nowrap ? 'flex-nowrap' : 'flex-wrap'}`}>
      {book.can_download && (
        <a className="g1-btn g1-btn--sm" href={downloadUrl(book.id)} download>
          <IconDownload className="g1-icon" aria-hidden />
          {t('books.download')}
        </a>
      )}
      {(done || built) && hasKindle && !book.delivered.includes('kindle') && (
        <button type="button" className="g1-btn g1-btn--sm" disabled={busy} onClick={() => onSend(book, 'kindle')}>
          <IconSend className="g1-icon" aria-hidden />
          {t('books.sendToKindle')}
        </button>
      )}
      {built && hasKindle && book.delivered.includes('kindle') && (
        <button type="button" className="g1-btn g1-btn--sm g1-btn--ghost" disabled={busy} onClick={() => setAsking('resend')}>
          <IconSend className="g1-icon" aria-hidden />
          {t('books.sendAgain')}
        </button>
      )}
      {!done && !built && (
        <button type="button" className="g1-btn g1-btn--sm" disabled={busy} onClick={() => onSend(book)}>
          <IconRefresh className="g1-icon" aria-hidden />
          {t('books.retry')}
        </button>
      )}
      {deletable && (
        <button
          type="button"
          className="g1-btn g1-btn--ghost g1-btn--sm"
          aria-label={t('books.deleteLabel', { title: book.title })}
          onClick={() => setAsking('delete')}
        >
          <IconTrash className="g1-icon" aria-hidden />
          {t('books.delete')}
        </button>
      )}
    </div>
  );
}

/** One book in a list: title, where it came from, where it went and what to do next. */
export function BookRow(props: {
  book: Book;
  hasKindle: boolean;
  busy: boolean;
  onSend: (book: Book, target?: Target) => void;
  deletable?: boolean;
}) {
  const { book } = props;
  const { t, lang } = useI18n();
  const hint = useArrivalHint();
  const meta = [
    book.minutes ? t('books.readMinutes', { n: book.minutes }) : null,
    book.can_download ? formatSize(book.size, lang) : null,
    formatDate(book.created_at, lang),
  ].filter(Boolean);
  const place = placeOf(book);
  const failed = place === 'failed' || place === 'interrupted';
  return (
    <li className="border-b border-line py-4 first:pt-0">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1 basis-64">
          <BookTitle book={book} />
          <p className="g1-meta mb-0 mt-1">
            <OriginalLink book={book} />
            {meta.map((item) => ` · ${item}`).join('')}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <BookBadges book={book} />
          <BookActions {...props} />
        </div>
      </div>
      {book.status === 'processing' && <ProgressStrip stage={book.stage} last={book.stage === 'sending' ? 'deliver' : 'preview'} />}
      {place === 'kindle' && hint && (
        <p className="m-0 mt-2">
          <NotArrivedLink book={book} />
        </p>
      )}
      {failed && (
        <p className="m-0 mt-2 text-sm text-muted" role="status">
          {failureText(book, t)}
          {book.detail && <span className="g1-meta mt-1 block">{book.detail}</span>}
        </p>
      )}
    </li>
  );
}
