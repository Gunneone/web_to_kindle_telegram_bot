import { useMutation } from '@tanstack/react-query';
import { Link } from 'react-router';
import { BookActions, BookRow, StatusBadge } from '../components/BookRow';
import { ErrorCallout } from '../components/Callout';
import { PageHead, Scribble } from '../components/Text';
import { useI18n } from '../i18n';
import { errorCode, resendBook, type Book, type Target } from '../lib/api';
import { useAllBooks, useRefreshBooks } from '../lib/books';
import { formatDate } from '../lib/format';
import { useMe } from '../lib/session';

export function History() {
  const { t, lang } = useI18n();
  const me = useMe();
  const refresh = useRefreshBooks();
  const books = useAllBooks();
  const resend = useMutation({
    mutationFn: ({ book, target }: { book: Book; target?: Target }) => resendBook(book.id, target),
    onSuccess: () => void refresh(),
  });

  const rows = books.data?.pages.flatMap((page) => page.books) ?? [];
  const total = books.data?.pages[0]?.total ?? 0;
  const hasKindle = Boolean(me?.kindle_email);

  return (
    <div className="g1-container">
      <PageHead eyebrow={t('history.eyebrow', { n: total })} title={t('history.title')} />
      <ErrorCallout code={errorCode(books.error) ?? errorCode(resend.error)} />
      {books.isSuccess && rows.length === 0 ? (
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
      ) : (
        <>
        <ul className="m-0 list-none p-0 sm:hidden">
          {rows.map((book) => (
            <BookRow
              key={book.id}
              book={book}
              hasKindle={hasKindle}
              busy={resend.isPending}
              onSend={(target_book, target) => resend.mutate({ book: target_book, target })}
            />
          ))}
        </ul>
        <div className="hidden overflow-x-auto sm:block">
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
              {rows.map((book) => (
                <tr key={book.id}>
                  <td className="max-w-[28rem]">
                    <a className="g1-link block truncate" href={book.url} target="_blank" rel="noopener noreferrer">
                      {book.title}
                    </a>
                    <span className="g1-meta">
                      {book.host}
                      {book.status === 'processing' && book.stage ? ` · ${t(`books.stage.${book.stage}`)}` : ''}
                    </span>
                    {(book.status === 'failed' || book.status === 'interrupted') && (
                      <span className="mt-1 block text-sm text-muted">
                        {book.status === 'interrupted'
                          ? t('books.interrupted')
                          : book.failure
                            ? t(`books.failure.${book.failure}`, { host: book.host })
                            : t('books.failure.generic')}
                      </span>
                    )}
                  </td>
                  <td className="g1-mono g1-num whitespace-nowrap">{formatDate(book.created_at, lang)}</td>
                  <td>
                    <StatusBadge status={book.status} />
                  </td>
                  <td>
                    <BookActions
                      book={book}
                      hasKindle={hasKindle}
                      busy={resend.isPending}
                      onSend={(target_book, target) => resend.mutate({ book: target_book, target })}
                    />
                  </td>
                </tr>
              ))}
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
