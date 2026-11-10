import { useMutation, useQueryClient } from '@tanstack/react-query';
import { IconArrowLeft, IconArrowUpRight, IconDownload, IconRefresh, IconSend } from '@tabler/icons-react';
import { Link, useParams } from 'react-router';
import { failureText, ProgressStrip, StatusBadge } from '../components/BookRow';
import { Callout, ErrorCallout } from '../components/Callout';
import { EReader } from '../components/EReader';
import { Feedback } from '../components/Feedback';
import { Eyebrow } from '../components/Text';
import { useI18n } from '../i18n';
import { downloadUrl, errorCode, previewUrl, resendBook, type Target } from '../lib/api';
import { useBook, useRefreshBooks } from '../lib/books';
import { formatDate, formatSize } from '../lib/format';
import { useMe, useSession } from '../lib/session';

/** One book: watch it being made, read it on a little e-reader, then send it, download it, or report a problem. */
export function BookPage() {
  const { id } = useParams();
  const bookId = Number(id);
  const { t, lang } = useI18n();
  const me = useMe();
  const session = useSession();
  const client = useQueryClient();
  const refresh = useRefreshBooks();
  const query = useBook(bookId);
  const send = useMutation({
    mutationFn: (target?: Target) => resendBook(bookId, target),
    onSuccess: (data) => {
      client.setQueryData(['books', 'one', bookId], data);
      void refresh();
    },
  });

  const back = (
    <Link className="g1-link inline-flex items-center gap-1 text-sm" to={me ? '/history' : '/'}>
      <IconArrowLeft className="g1-icon" aria-hidden />
      {me ? t('book.allBooks') : t('book.another')}
    </Link>
  );

  const book = query.data?.book;
  if (!book) {
    return (
      <div className="g1-container g1-stack">
        {query.isPending ? <p className="g1-meta">{t('common.loading')}</p> : <ErrorCallout code={errorCode(query.error)} />}
        {!query.isPending && !me && errorCode(query.error) === 'UNAUTHENTICATED' && (
          <div>
            <Link className="g1-btn g1-btn--primary" to={`/signin?next=${encodeURIComponent(`/books/${bookId}`)}`}>
              {t('book.guestAction')}
            </Link>
          </div>
        )}
        <div>{back}</div>
      </div>
    );
  }

  const hasKindle = Boolean(me?.kindle_email);
  const guest = !me;
  const working = book.status === 'processing';
  // Sending a book that is already built: keep it on the screen while it goes out
  const delivering = working && (book.stage === 'sending' || (send.variables !== undefined && !send.isError));
  const building = working && !delivering;
  const failed = book.status === 'failed' || book.status === 'interrupted';
  const showBook = book.can_download || delivering;
  const onKindle = !working && book.delivered.includes('kindle');
  const meta = [
    book.minutes ? t('books.readMinutes', { n: book.minutes }) : null,
    book.can_download ? formatSize(book.size, lang) : null,
    formatDate(book.created_at, lang),
  ].filter(Boolean);

  return (
    <div className="g1-container">
      <div className="mb-6">{back}</div>
      <div className="grid items-start gap-8 md:grid-cols-[minmax(0,340px)_minmax(0,1fr)]">
        <div className="flex flex-col items-center gap-3 md:sticky md:top-20">
          <EReader src={showBook ? previewUrl(book.id) : undefined} title={t('book.reader', { title: book.title })}>
            {building ? (
              <>
                <span>{t('book.building')}</span>
                <ProgressStrip stage={book.stage} last="preview" />
              </>
            ) : (
              <span>{failed ? failureText(book, t) : t('books.status.processing')}</span>
            )}
          </EReader>
          {showBook && <p className="m-0 max-w-[340px] text-center text-xs text-muted">{t('book.readerHint')}</p>}
        </div>

        <div className="g1-stack min-w-0">
          <header>
            <Eyebrow>{t('book.eyebrow', { host: book.host })}</Eyebrow>
            <h1 className="g1-title mt-2 break-words">{book.title}</h1>
            <p className="g1-meta mb-0 mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
              <StatusBadge status={book.status} />
              {meta.length > 0 && <span>{meta.join(' · ')}</span>}
              <a className="g1-link inline-flex items-center gap-1" href={book.url} target="_blank" rel="noopener noreferrer">
                {t('books.openOriginal')}
                <IconArrowUpRight className="g1-icon" aria-hidden />
              </a>
            </p>
          </header>

          {book.paywalled && <Callout tone="info">{t('books.previewNote')}</Callout>}

          {onKindle && me?.kindle_email && (
            <Callout tone="success" title={t('books.onKindle')}>
              {t('book.sentTo', { email: me.kindle_email })}
            </Callout>
          )}

          {book.status === 'ready' && (
            <div>
              <h2 className="m-0 text-lg">{t('book.readyTitle')}</h2>
              <p className="m-0 mt-1 text-muted">{t('book.readyText')}</p>
            </div>
          )}

          {delivering && <ProgressStrip stage={book.stage} />}

          {failed && book.can_download && <Callout tone="warning">{failureText(book, t)}</Callout>}
          {failed && book.detail && <p className="g1-meta m-0">{book.detail}</p>}

          <div className="flex flex-wrap gap-3">
            {book.can_download && hasKindle && !onKindle && (
              <button
                type="button"
                className="g1-btn g1-btn--primary"
                disabled={working || send.isPending}
                onClick={() => send.mutate('kindle')}
              >
                <IconSend className="g1-icon" aria-hidden />
                {t('books.sendToKindle')}
              </button>
            )}
            {book.can_download && (
              <a
                className={hasKindle && !onKindle ? 'g1-btn' : 'g1-btn g1-btn--primary'}
                href={downloadUrl(book.id)}
                download
              >
                <IconDownload className="g1-icon" aria-hidden />
                {t('book.downloadEpub')}
              </a>
            )}
            {failed && !book.can_download && (
              <button type="button" className="g1-btn g1-btn--primary" disabled={send.isPending} onClick={() => send.mutate(undefined)}>
                <IconRefresh className="g1-icon" aria-hidden />
                {t('books.retry')}
              </button>
            )}
          </div>

          {book.can_download && guest && (
            <Callout tone="info" title={t('book.guestTitle')}>
              {t('book.guestText')}
              <div className="mt-3">
                <Link className="g1-btn g1-btn--sm g1-btn--primary" to={`/signin?next=${encodeURIComponent(`/books/${book.id}`)}`}>
                  {t('book.guestAction')}
                </Link>
              </div>
            </Callout>
          )}
          {book.can_download && !guest && !hasKindle && (
            <p className="m-0 text-sm text-muted">
              {t('book.noKindle')}{' '}
              <Link className="g1-link" to="/setup">
                {t('book.setupLink')}
              </Link>
            </p>
          )}

          <ErrorCallout code={errorCode(send.error)} />

          {showBook && me && session.data?.feedback && (
            <div className="border-t border-line pt-5">
              <Feedback bookId={book.id} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
