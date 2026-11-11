import { useMutation, useQueryClient } from '@tanstack/react-query';
import { IconArrowLeft, IconArrowUpRight, IconDownload, IconRefresh, IconSend } from '@tabler/icons-react';
import { useEffect } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router';
import { ArrivalReasons } from '../components/ArrivalHelp';
import { BookBadges, DeleteBook, failureText, ProgressStrip, SendAgain, type FromState } from '../components/BookRow';
import { Callout, ErrorCallout } from '../components/Callout';
import { EReader } from '../components/EReader';
import { Feedback } from '../components/Feedback';
import { Eyebrow } from '../components/Text';
import { UnconfirmedNote } from '../components/Unconfirmed';
import { useI18n } from '../i18n';
import { downloadUrl, errorCode, previewUrl, resendBook, type Target } from '../lib/api';
import { useBook, useRefreshBooks } from '../lib/books';
import { formatDate, formatSize } from '../lib/format';
import { useMe, useSession } from '../lib/session';
import { usePageTitle } from '../lib/title';

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
  usePageTitle(query.data?.book?.title ?? t('titles.book'));
  const location = useLocation();
  const navigate = useNavigate();
  // Arriving from "not on your Kindle?": the help is opened, and scrolled to once the book is there
  const loaded = query.data !== undefined;
  useEffect(() => {
    if (loaded && location.hash === '#not-arrived') document.getElementById('not-arrived')?.scrollIntoView({ block: 'start' });
  }, [loaded, location.hash]);
  const send = useMutation({
    mutationFn: (target?: Target) => resendBook(bookId, target),
    onSuccess: (data) => {
      client.setQueryData(['books', 'one', bookId], data);
      void refresh();
    },
  });

  // Back to where the book was opened from: Send or the library (with its search), else the library
  const from = (location.state as FromState | null)?.from;
  const backTo = !me ? '/' : from === '/' || from?.startsWith('/history') ? from : '/history';
  const back = (
    <Link className="g1-link inline-flex items-center gap-1 text-sm" to={backTo}>
      <IconArrowLeft className="g1-icon" aria-hidden />
      {!me ? t('book.another') : backTo === '/' ? t('book.backToSend') : t('book.backToLibrary')}
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
  const helpOpen = location.hash === '#not-arrived';
  const meta = [
    book.minutes ? t('books.readMinutes', { n: book.minutes }) : null,
    book.can_download ? formatSize(book.size, lang) : null,
    formatDate(book.created_at, lang),
  ].filter(Boolean);

  return (
    <div className="g1-container">
      <div className="mb-6">{back}</div>
      {/*
        On a phone the title and the buttons come first and the e-reader follows, so "Send to Kindle" isn't
        a screen away; from md the e-reader stands on the left, next to both blocks on the right.
      */}
      <div className="grid items-start gap-8 md:grid-cols-[minmax(0,340px)_minmax(0,1fr)] md:grid-rows-[auto_1fr]">
        <div className="g1-stack min-w-0 md:col-start-2 md:row-start-1">
          <header>
            <Eyebrow>{t('book.eyebrow', { host: book.host })}</Eyebrow>
            <h1 className="g1-title mt-2 break-words">{book.title}</h1>
            <p className="g1-meta mb-0 mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
              <BookBadges book={book} />
              {meta.length > 0 && <span>{meta.join(' · ')}</span>}
              <a className="g1-link inline-flex items-center gap-1" href={book.url} target="_blank" rel="noopener noreferrer">
                {t('books.openOriginal')}
                <IconArrowUpRight className="g1-icon" aria-hidden />
              </a>
            </p>
          </header>

          {book.paywalled && <Callout tone="info">{t('books.previewNote')}</Callout>}

          {onKindle && me?.kindle_email && (
            <Callout tone="success" title={t('book.sentTitle')}>
              {t('book.sentTo', { email: me.kindle_email })}
            </Callout>
          )}
          {onKindle && me?.kindle_email && (
            <details id="not-arrived" className="g1-card scroll-mt-24" open={helpOpen || undefined}>
              <summary className="cursor-pointer font-medium">{t('books.notArrived')}</summary>
              <div className="g1-stack mt-3">
                <p className="m-0 text-muted">{t('book.helpText')}</p>
                <h3 className="m-0 text-base">{t('setup.test.helpTitle')}</h3>
                <ArrivalReasons me={me} />
                {book.can_download && hasKindle && (
                  <div className="g1-stack">
                    <p className="m-0 text-muted">{t('book.helpResend')}</p>
                    <div>
                      <SendAgain book={book} busy={working || send.isPending} onConfirm={() => send.mutate('kindle')} />
                    </div>
                  </div>
                )}
                <div className="flex flex-wrap gap-2">
                  <Link className="g1-btn g1-btn--sm" to="/setup?step=test">
                    {t('book.helpTest')}
                  </Link>
                  <Link className="g1-btn g1-btn--sm g1-btn--ghost" to="/setup?step=address">
                    {t('setup.test.fixAddress')}
                  </Link>
                </div>
              </div>
            </details>
          )}

          {book.status === 'ready' && !guest && (
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
            {/* Downloading needs an account; a visitor gets the preview and a way to sign in */}
            {book.can_download && !guest && (
              <a
                className={hasKindle && !onKindle ? 'g1-btn' : 'g1-btn g1-btn--primary'}
                href={downloadUrl(book.id)}
                download
              >
                <IconDownload className="g1-icon" aria-hidden />
                {t('book.downloadEpub')}
              </a>
            )}
            {book.can_download && hasKindle && onKindle && (
              <SendAgain book={book} busy={working || send.isPending} onConfirm={() => send.mutate('kindle')} />
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

          {book.can_download && hasKindle && !onKindle && !working && <UnconfirmedNote />}

          <ErrorCallout code={errorCode(send.error)} />
        </div>

        <div className="flex flex-col items-center gap-3 md:sticky md:top-20 md:col-start-1 md:row-span-2 md:row-start-1">
          <EReader src={showBook ? previewUrl(book.id) : undefined} title={t('book.reader', { title: book.title })}>
            {building ? (
              <>
                <span>{t('book.building')}</span>
                <ProgressStrip stage={book.stage} last="preview" />
              </>
            ) : (
              <span>{failed ? failureText(book, t) : t('books.place.processing')}</span>
            )}
          </EReader>
          {showBook && <p className="m-0 max-w-[340px] text-center text-xs text-muted">{t('book.readerHint')}</p>}
        </div>

        <div className="g1-stack min-w-0 md:col-start-2 md:row-start-2">
          {!working && (
            <div>
              <DeleteBook book={book} onDeleted={() => navigate(backTo, { replace: true })} />
            </div>
          )}

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
