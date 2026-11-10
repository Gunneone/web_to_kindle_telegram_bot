import { IconArrowUpRight, IconDownload, IconRefresh, IconSend } from '@tabler/icons-react';
import { Link } from 'react-router';
import { useI18n, type MessageKey } from '../i18n';
import { downloadUrl, type Book, type BookStatus, type Stage, type Target } from '../lib/api';
import { formatDate, formatSize } from '../lib/format';

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

const BADGE: Record<BookStatus, string> = {
  processing: 'g1-badge g1-badge--soft',
  ready: 'g1-badge',
  sent: 'g1-badge g1-badge--primary',
  preview: 'g1-badge g1-badge--soft',
  failed: 'g1-badge text-danger [--g1-edge:var(--g1-danger)]',
  interrupted: 'g1-badge text-warning [--g1-edge:var(--g1-warning)]',
};

export function StatusBadge({ status }: { status: BookStatus }) {
  const { t } = useI18n();
  return <span className={BADGE[status]}>{t(`books.status.${status}`)}</span>;
}

export function failureText(book: Book, t: (key: MessageKey, vars?: Record<string, string>) => string): string {
  if (book.status === 'interrupted') return t('books.interrupted');
  const key = (book.failure ? `books.failure.${book.failure}` : 'books.failure.generic') as MessageKey;
  return t(key, { host: book.host });
}

/** The book's title, opening it in Eselsohr, and a small link to the page it came from. */
export function BookTitle({ book, className = '' }: { book: Book; className?: string }) {
  const { t } = useI18n();
  return (
    <span className={`flex min-w-0 items-center gap-2 ${className}`}>
      <Link className="g1-link min-w-0 truncate font-medium" to={`/books/${book.id}`}>
        {book.title}
      </Link>
      <a
        className="shrink-0 text-muted hover:text-fg"
        href={book.url}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={t('books.openOriginal')}
        title={t('books.openOriginal')}
      >
        <IconArrowUpRight className="g1-icon" aria-hidden />
      </a>
    </span>
  );
}

/** Download, send to Kindle, or try again: whatever makes sense for this book. */
export function BookActions({
  book,
  hasKindle,
  busy,
  onSend,
}: {
  book: Book;
  hasKindle: boolean;
  busy: boolean;
  /** No target: make the book again without delivering it */
  onSend: (book: Book, target?: Target) => void;
}) {
  const { t } = useI18n();
  if (book.status === 'processing') return null;
  const done = book.status === 'ready' || book.status === 'sent' || book.status === 'preview';
  return (
    <div className="flex flex-wrap items-center gap-2">
      {book.can_download && (
        <a className="g1-btn g1-btn--sm" href={downloadUrl(book.id)} download>
          <IconDownload className="g1-icon" aria-hidden />
          {t('books.download')}
        </a>
      )}
      {done && hasKindle && !book.delivered.includes('kindle') && (
        <button type="button" className="g1-btn g1-btn--sm" disabled={busy} onClick={() => onSend(book, 'kindle')}>
          <IconSend className="g1-icon" aria-hidden />
          {t('books.sendToKindle')}
        </button>
      )}
      {!done && (
        <button
          type="button"
          className="g1-btn g1-btn--sm"
          disabled={busy}
          onClick={() => onSend(book)}
        >
          <IconRefresh className="g1-icon" aria-hidden />
          {t('books.retry')}
        </button>
      )}
    </div>
  );
}

/** One book in a list: title, where it came from, its state and what to do next. */
export function BookRow(props: {
  book: Book;
  hasKindle: boolean;
  busy: boolean;
  onSend: (book: Book, target?: Target) => void;
}) {
  const { book } = props;
  const { t, lang } = useI18n();
  const meta = [
    book.host,
    book.minutes ? t('books.readMinutes', { n: book.minutes }) : null,
    book.can_download ? formatSize(book.size, lang) : null,
    formatDate(book.created_at, lang),
  ].filter(Boolean);
  const failed = book.status === 'failed' || book.status === 'interrupted';
  return (
    <li className="border-b border-line py-4 first:pt-0">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1 basis-64">
          <BookTitle book={book} />
          <p className="g1-meta mb-0 mt-1">{meta.join(' · ')}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={book.status} />
          <BookActions {...props} />
        </div>
      </div>
      {book.status === 'processing' && <ProgressStrip stage={book.stage} last={book.stage === 'sending' ? 'deliver' : 'preview'} />}
      {book.status === 'sent' && book.delivered.length > 0 && (
        <p className="g1-meta mb-0 mt-2">
          {book.delivered.includes('kindle') ? t('books.onKindle') : t('books.readyToDownload')}
        </p>
      )}
      {book.status === 'preview' && <p className="m-0 mt-2 text-sm text-muted">{t('books.previewNote')}</p>}
      {failed && (
        <p className="m-0 mt-2 text-sm text-muted" role="status">
          {failureText(book, t)}
          {book.detail && <span className="g1-meta mt-1 block">{book.detail}</span>}
        </p>
      )}
    </li>
  );
}
