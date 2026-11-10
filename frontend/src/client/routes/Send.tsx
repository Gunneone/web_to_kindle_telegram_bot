import { useMutation } from '@tanstack/react-query';
import { IconArrowRight, IconBookmark, IconBrandTelegram, IconDeviceMobile, IconSend } from '@tabler/icons-react';
import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router';
import { BookRow } from '../components/BookRow';
import { Callout, ErrorCallout } from '../components/Callout';
import { PasteButton } from '../components/PasteButton';
import { PageHead, SectionHead } from '../components/Text';
import { useI18n } from '../i18n';
import { ApiError, createBook, errorCode, resendBook, updateMe, type Book, type Target } from '../lib/api';
import { useRecentBooks, useRefreshBooks } from '../lib/books';
import { formatDate } from '../lib/format';
import { bookmarklet, extractLinks, MAX_LINKS } from '../lib/links';
import { useMe, useSetUser } from '../lib/session';

interface Duplicate {
  book: Book;
  url: string;
}

interface Started {
  started: Book[];
  duplicates: Duplicate[];
  failures: { url: string; code: string }[];
  target?: Target;
  dropped: number;
}

/**
 * The signed-in start page. With a Kindle set up, a link goes straight to it ("Send to Kindle") or is
 * opened for a look first; without one, the book is made to look at and download. Several links at once
 * are started one after the other and followed in the list below.
 */
export function Send({ initialLink = '' }: { initialLink?: string }) {
  const { t, lang } = useI18n();
  const me = useMe();
  const setUser = useSetUser();
  const navigate = useNavigate();
  const refresh = useRefreshBooks();
  const recent = useRecentBooks();
  const input = useRef<HTMLInputElement>(null);
  const primary = useRef<HTMLButtonElement>(null);
  const [url, setUrl] = useState(initialLink);
  const [result, setResult] = useState<Started | null>(null);
  const hasKindle = Boolean(me?.kindle_email);
  const pocketbook = me?.device === 'pocketbook';

  // A link handed over by the bookmarklet or the share sheet is one keypress from going out
  useEffect(() => (initialLink ? primary.current : input.current)?.focus(), [initialLink]);

  const start = useMutation({
    mutationFn: async ({ links, target, dropped }: { links: string[]; target?: Target; dropped: number }) => {
      const outcome: Started = { started: [], duplicates: [], failures: [], target, dropped };
      for (const link of links) {
        try {
          outcome.started.push((await createBook(link, false, target)).book);
        } catch (error) {
          if (error instanceof ApiError && error.code === 'DUPLICATE') {
            outcome.duplicates.push({ book: error.extra.book as Book, url: link });
          } else {
            outcome.failures.push({ url: link, code: errorCode(error) ?? 'UNKNOWN' });
          }
        }
      }
      return outcome;
    },
    onSuccess: (outcome, { links }) => {
      void refresh();
      if (outcome.started.length > 0) setUrl('');
      const only = outcome.started[0];
      // One book to look at first: open it
      if (!outcome.target && links.length === 1 && only) {
        void navigate(`/books/${only.id}`);
        return;
      }
      setResult(outcome);
    },
  });
  // "Make it again" on a link that already went out: only that one, the other results stay
  const redo = useMutation({
    mutationFn: (duplicate: Duplicate) => createBook(duplicate.url, true, result?.target),
    onSuccess: ({ book }, duplicate) => {
      void refresh();
      if (!result?.target && result?.duplicates.length === 1 && result.started.length === 0) {
        void navigate(`/books/${book.id}`);
        return;
      }
      setResult((current) =>
        current && {
          ...current,
          started: [...current.started, book],
          duplicates: current.duplicates.filter((d) => d !== duplicate),
        },
      );
    },
  });
  const resend = useMutation({
    mutationFn: ({ book, target }: { book: Book; target?: Target }) => resendBook(book.id, target),
    onSuccess: () => void refresh(),
  });
  const downloadOnly = useMutation({
    mutationFn: () => updateMe({ download_only: true }),
    onSuccess: ({ user }) => setUser(user),
  });

  const go = (target?: Target) => {
    const all = extractLinks(url);
    if (all.length === 0) return;
    setResult(null);
    const links = all.slice(0, MAX_LINKS);
    start.mutate({ links, target, dropped: all.length - links.length });
  };
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    go(hasKindle ? 'kindle' : undefined);
  };

  const books = recent.data?.books ?? [];
  const failures = result?.failures ?? [];
  const singleFailure = failures.length === 1 && (result?.started.length ?? 0) + (result?.duplicates.length ?? 0) === 0;
  const showSetup = me && !hasKindle && !me.download_only;

  return (
    <div className="g1-container">
      <PageHead eyebrow={t('send.eyebrow')} title={t('send.title')} lead={hasKindle ? t('send.lead') : t('send.leadNoKindle')} />

      {showSetup && (
        <div className="g1-card mb-6">
          <h2 className="g1-card__title m-0">{t('send.setupTitle')}</h2>
          <p className="g1-card__text m-0">{t('send.setupText')}</p>
          <div className="g1-card__foot flex flex-wrap gap-2">
            <Link to="/setup" className="g1-btn g1-btn--primary">
              {t('send.setupAction')} <IconArrowRight className="g1-icon g1-arrow" aria-hidden />
            </Link>
            <button type="button" className="g1-btn g1-btn--ghost" disabled={downloadOnly.isPending} onClick={() => downloadOnly.mutate()}>
              {t('send.noKindleAction')}
            </button>
          </div>
          <ErrorCallout code={errorCode(downloadOnly.error)} />
        </div>
      )}

      {hasKindle && !me?.setup_verified && (
        <div className="mb-5">
          <Callout tone="info">
            {t('send.unverified')}{' '}
            <Link className="g1-link" to="/setup">
              {t('send.finishSetup')}
            </Link>
          </Callout>
        </div>
      )}

      <form onSubmit={submit} className="g1-stack">
        <div>
          <label className="g1-label" htmlFor="send-url">
            {t('send.label')}
          </label>
          <div className="flex gap-2">
            <input
              id="send-url"
              ref={input}
              className="g1-input min-w-0 flex-1"
              type="text"
              inputMode="url"
              autoComplete="off"
              spellCheck={false}
              aria-describedby="send-url-hint"
              placeholder={t('send.placeholder')}
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              required
            />
            <PasteButton onPaste={setUrl} />
          </div>
          <span id="send-url-hint" className="mt-1 block text-sm text-muted">
            {t('send.hint', { n: MAX_LINKS })}
          </span>
        </div>
        <div className="flex flex-wrap gap-3">
          <button ref={primary} type="submit" className="g1-btn g1-btn--primary" disabled={!url.trim() || start.isPending}>
            {hasKindle && <IconSend className="g1-icon" aria-hidden />}
            {start.isPending
              ? t('send.making')
              : hasKindle
                ? t(pocketbook ? 'send.sendToPocketbook' : 'send.sendToKindle')
                : t('send.make')}
          </button>
          {hasKindle && (
            <button type="button" className="g1-btn" disabled={!url.trim() || start.isPending} onClick={() => go(undefined)}>
              {t('send.previewFirst')}
            </button>
          )}
        </div>

        {result && result.started.length > 0 && (
          <Callout tone="success">
            {result.started.length === 1 ? t('send.startedOne') : t('send.startedMany', { n: result.started.length })}
          </Callout>
        )}
        {result && result.dropped > 0 && <Callout tone="warning">{t('send.tooMany', { n: MAX_LINKS })}</Callout>}
        {result?.duplicates.map((duplicate) => (
          <Callout
            key={duplicate.url}
            tone="info"
            title={
              result.duplicates.length + result.started.length > 1
                ? t('send.duplicateNamed', { title: duplicate.book.title, date: formatDate(duplicate.book.created_at, lang) })
                : t('send.duplicateTitle', { date: formatDate(duplicate.book.created_at, lang) })
            }
          >
            {t('send.duplicateText')}
            <div className="mt-3 flex flex-wrap gap-2">
              {duplicate.book.can_download && (
                <Link className="g1-btn g1-btn--sm" to={`/books/${duplicate.book.id}`}>
                  {t('send.openIt')}
                </Link>
              )}
              <button type="button" className="g1-btn g1-btn--sm" disabled={redo.isPending} onClick={() => redo.mutate(duplicate)}>
                {t('send.sendAgain')}
              </button>
            </div>
          </Callout>
        ))}
        {singleFailure ? (
          <ErrorCallout code={failures[0].code} />
        ) : (
          failures.length > 0 && (
            <Callout tone="danger" title={t('send.failedLinks')}>
              <ul className="m-0 mt-1 pl-5">
                {failures.map((failure) => (
                  <li key={failure.url} className="break-all">
                    <span className="g1-mono text-sm">{failure.url}</span>: <ErrorText code={failure.code} />
                  </li>
                ))}
              </ul>
            </Callout>
          )
        )}
        <ErrorCallout code={errorCode(start.error) ?? errorCode(redo.error) ?? errorCode(resend.error)} />
      </form>

      <section className="g1-section">
        <SectionHead
          eyebrow={t('send.recentEyebrow')}
          title={t('send.recentTitle')}
          action={
            books.length > 0 ? (
              <Link className="g1-link" to="/history">
                {t('send.allHistory')} <IconArrowRight className="g1-icon g1-arrow" aria-hidden />
              </Link>
            ) : undefined
          }
        />
        {books.length === 0 ? (
          !recent.isPending && <p className="text-muted">{t('send.recentEmpty')}</p>
        ) : (
          <ul className="m-0 list-none p-0">
            {books.map((book) => (
              <BookRow
                key={book.id}
                book={book}
                hasKindle={hasKindle}
                busy={resend.isPending}
                onSend={(target_book, target) => resend.mutate({ book: target_book, target })}
              />
            ))}
          </ul>
        )}
      </section>

      <Shortcuts />
    </div>
  );
}

function ErrorText({ code }: { code: string }) {
  const { error } = useI18n();
  return <>{error(code)}</>;
}

/** Ways to send without opening this page first: a bookmarklet, the phone's share sheet, the bot. */
function Shortcuts() {
  const { t } = useI18n();
  const link = useRef<HTMLAnchorElement>(null);
  const [hint, setHint] = useState(false);

  // React refuses javascript: links in markup, so the bookmarklet is set on the element itself
  useEffect(() => {
    link.current?.setAttribute('href', bookmarklet(window.location.origin));
  }, []);

  return (
    <section className="g1-section">
      <SectionHead eyebrow={t('shortcuts.eyebrow')} title={t('shortcuts.title')} />
      <div className="g1-grid">
        <div className="g1-card">
          <IconBookmark className="g1-icon text-primary" aria-hidden />
          <h3 className="g1-card__title m-0">{t('shortcuts.bookmarklet.title')}</h3>
          <p className="g1-card__text m-0">{t('shortcuts.bookmarklet.text')}</p>
          <div className="g1-card__foot">
            <a
              ref={link}
              className="g1-btn g1-btn--sm esel-bookmarklet"
              onClick={(event) => {
                event.preventDefault();
                setHint(true);
              }}
            >
              {t('shortcuts.bookmarklet.button')}
            </a>
          </div>
          {hint && (
            <p className="m-0 text-sm text-muted" role="status">
              {t('shortcuts.bookmarklet.clickHint')}
            </p>
          )}
        </div>
        <div className="g1-card">
          <IconDeviceMobile className="g1-icon text-primary" aria-hidden />
          <h3 className="g1-card__title m-0">{t('shortcuts.phone.title')}</h3>
          <p className="g1-card__text m-0">{t('shortcuts.phone.text')}</p>
        </div>
        <div className="g1-card">
          <IconBrandTelegram className="g1-icon text-primary" aria-hidden />
          <h3 className="g1-card__title m-0">{t('shortcuts.bot.title')}</h3>
          <p className="g1-card__text m-0">{t('shortcuts.bot.text')}</p>
          <div className="g1-card__foot">
            <a className="g1-link" href="https://t.me/SubstackKindleBot" target="_blank" rel="noopener noreferrer">
              {t('shortcuts.bot.action')}
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}
