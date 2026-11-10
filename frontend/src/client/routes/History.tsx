import { useMutation } from '@tanstack/react-query';
import { IconSearch } from '@tabler/icons-react';
import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { BookActions, BookBadges, BookRow, BookTitle, failureText, NotArrivedLink } from '../components/BookRow';
import { ErrorCallout } from '../components/Callout';
import { PageHead, Scribble } from '../components/Text';
import { UnconfirmedCallout } from '../components/Unconfirmed';
import { useI18n } from '../i18n';
import { errorCode, HISTORY_SHOWS, resendBook, type Book, type HistoryShow, type Target } from '../lib/api';
import { placeOf, useAllBooks, useArrivalHint, useRefreshBooks } from '../lib/books';
import { formatDate } from '../lib/format';
import { useMe } from '../lib/session';

const SEARCH_DELAY_MS = 250;

const asShow = (value: string | null): HistoryShow | '' =>
  (HISTORY_SHOWS as readonly string[]).includes(value ?? '') ? (value as HistoryShow) : '';

export function History() {
  const { t, lang } = useI18n();
  const me = useMe();
  const refresh = useRefreshBooks();
  const hint = useArrivalHint();
  // The search and filter live in the address, so the way back from a book returns to the same list
  const [params, setParams] = useSearchParams();
  const search = params.get('q') ?? '';
  const show = asShow(params.get('show'));
  const [typed, setTyped] = useState(search);
  const books = useAllBooks(search, show);
  const resend = useMutation({
    mutationFn: ({ book, target }: { book: Book; target?: Target }) => resendBook(book.id, target),
    onSuccess: () => void refresh(),
  });

  const update = (changes: Record<string, string>) =>
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        for (const [key, value] of Object.entries(changes)) {
          if (value) next.set(key, value);
          else next.delete(key);
        }
        return next;
      },
      { replace: true },
    );

  useEffect(() => {
    if (typed.trim() === search) return;
    const timer = setTimeout(() => update({ q: typed.trim() }), SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
  }, [typed, search]);

  const rows = books.data?.pages.flatMap((page) => page.books) ?? [];
  const total = books.data?.pages[0]?.total ?? 0;
  const hasKindle = Boolean(me?.kindle_email);
  const filtered = Boolean(search || show);
  const onSend = (target_book: Book, target?: Target) => resend.mutate({ book: target_book, target });

  return (
    <div className="g1-container">
      <PageHead eyebrow={t('history.eyebrow', { n: total })} title={t('history.title')} />
      {hasKindle && !me?.setup_verified && rows.length > 0 && (
        <div className="mb-6">
          <UnconfirmedCallout />
        </div>
      )}
      {(filtered || rows.length > 0) && (
        <form
          role="search"
          className="mb-6 flex flex-wrap items-end gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            update({ q: typed.trim() });
          }}
        >
          <div className="min-w-0 flex-1 basis-56">
            <label className="g1-label" htmlFor="history-search">
              {t('history.search')}
            </label>
            <div className="relative">
              <IconSearch className="g1-icon pointer-events-none absolute left-3 z-10 top-1/2 -translate-y-1/2 text-muted" aria-hidden />
              <input
                id="history-search"
                className="g1-input pl-10"
                type="search"
                placeholder={t('history.searchPlaceholder')}
                value={typed}
                onChange={(event) => setTyped(event.target.value)}
              />
            </div>
          </div>
          <div className="basis-44">
            <label className="g1-label" htmlFor="history-show">
              {t('history.show')}
            </label>
            <select
              id="history-show"
              className="g1-select"
              value={show}
              onChange={(event) => update({ show: event.target.value })}
            >
              <option value="">{t('history.shows.all')}</option>
              {HISTORY_SHOWS.map((value) => (
                <option key={value} value={value}>
                  {t(`history.shows.${value}`)}
                </option>
              ))}
            </select>
          </div>
        </form>
      )}
      <ErrorCallout code={errorCode(books.error) ?? errorCode(resend.error)} />
      {books.isSuccess && rows.length === 0 ? (
        filtered ? (
          <div className="g1-card">
            <h2 className="g1-card__title m-0">{t('history.noMatches')}</h2>
            <p className="g1-card__text m-0">{t('history.noMatchesText')}</p>
            <div className="g1-card__foot">
              <button
                type="button"
                className="g1-btn"
                onClick={() => {
                  setTyped('');
                  update({ q: '', show: '' });
                }}
              >
                {t('history.showAll')}
              </button>
            </div>
          </div>
        ) : (
          <div className="g1-card">
            <h2 className="g1-card__title m-0">{t('history.empty')}</h2>
            <p className="g1-card__text m-0">
              {t('history.emptyText')} <Scribble>{t('history.emptyScribble')}</Scribble>
            </p>
            <div className="g1-card__foot">
              <Link to="/" className="g1-btn g1-btn--primary">
                {t('history.emptyAction')}
              </Link>
            </div>
          </div>
        )
      ) : (
        <>
          <ul className="m-0 list-none p-0 lg:hidden">
            {rows.map((book) => (
              <BookRow key={book.id} book={book} hasKindle={hasKindle} busy={resend.isPending} onSend={onSend} deletable />
            ))}
          </ul>
          <div className="hidden overflow-x-auto lg:block">
            <table className="g1-table">
              <thead>
                <tr>
                  <th>{t('history.columns.title')}</th>
                  <th>{t('history.columns.date')}</th>
                  <th>{t('history.columns.status')}</th>
                  <th>{t('history.columns.actions')}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((book) => {
                  const place = placeOf(book);
                  return (
                    <tr key={book.id}>
                      <td className="max-w-[28rem]">
                        <BookTitle book={book} />
                        <span className="g1-meta">
                          {book.host}
                          {book.status === 'processing' && book.stage ? ` · ${t(`books.stage.${book.stage}`)}` : ''}
                        </span>
                        {(place === 'failed' || place === 'interrupted') && (
                          <span className="mt-1 block text-sm text-muted">{failureText(book, t)}</span>
                        )}
                      </td>
                      <td className="g1-mono g1-num whitespace-nowrap">{formatDate(book.created_at, lang)}</td>
                      <td>
                        <BookBadges book={book} />
                        {place === 'kindle' && hint && (
                          <span className="mt-1 block whitespace-nowrap">
                            <NotArrivedLink book={book} />
                          </span>
                        )}
                      </td>
                      <td>
                        <BookActions book={book} hasKindle={hasKindle} busy={resend.isPending} onSend={onSend} deletable nowrap />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
      {books.hasNextPage && (
        <div className="mt-5">
          <button type="button" className="g1-btn" disabled={books.isFetchingNextPage} onClick={() => void books.fetchNextPage()}>
            {t('history.more')}
          </button>
        </div>
      )}
    </div>
  );
}
