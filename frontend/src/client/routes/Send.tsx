import { useMutation } from '@tanstack/react-query';
import { IconArrowRight } from '@tabler/icons-react';
import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router';
import { BookRow } from '../components/BookRow';
import { Callout, ErrorCallout } from '../components/Callout';
import { PageHead, SectionHead } from '../components/Text';
import { useI18n } from '../i18n';
import { ApiError, createBook, errorCode, resendBook, type Book, type Target } from '../lib/api';
import { useRecentBooks, useRefreshBooks } from '../lib/books';
import { formatDate } from '../lib/format';
import { useMe } from '../lib/session';

interface Duplicate {
  book: Book;
  url: string;
}

/** The signed-in start page: paste a link and the book is made, then opened for a look before it goes anywhere. */
export function Send() {
  const { t, lang } = useI18n();
  const me = useMe();
  const navigate = useNavigate();
  const refresh = useRefreshBooks();
  const recent = useRecentBooks();
  const input = useRef<HTMLInputElement>(null);
  const [url, setUrl] = useState('');
  const [duplicate, setDuplicate] = useState<Duplicate | null>(null);
  const hasKindle = Boolean(me?.kindle_email);

  useEffect(() => input.current?.focus(), []);

  const create = useMutation({
    mutationFn: ({ link, force }: { link: string; force: boolean }) => createBook(link, force),
    onSuccess: ({ book }) => {
      setUrl('');
      setDuplicate(null);
      void refresh();
      void navigate(`/books/${book.id}`);
    },
    onError: (error, { link }) => {
      if (error instanceof ApiError && error.code === 'DUPLICATE') {
        setDuplicate({ book: error.extra.book as Book, url: link });
      }
    },
  });
  const resend = useMutation({
    mutationFn: ({ book, target }: { book: Book; target?: Target }) => resendBook(book.id, target),
    onSuccess: () => void refresh(),
  });

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setDuplicate(null);
    create.mutate({ link: url.trim(), force: false });
  };

  const createCode = errorCode(create.error);
  const code = createCode === 'DUPLICATE' ? errorCode(resend.error) : (createCode ?? errorCode(resend.error));
  const books = recent.data?.books ?? [];

  return (
    <div className="g1-container">
      <PageHead eyebrow={t('send.eyebrow')} title={t('send.title')} lead={t('send.lead')} />

      {!hasKindle && (
        <div className="mb-5">
          <Callout tone="info" title={t('send.noKindleTitle')}>
            {t('send.noKindleText')}{' '}
            <Link className="g1-link" to="/settings">
              {t('send.openSettings')}
            </Link>
          </Callout>
        </div>
      )}

      <form onSubmit={submit} className="g1-stack">
        <div>
          <label className="g1-label" htmlFor="send-url">
            {t('send.label')}
          </label>
          <input
            id="send-url"
            ref={input}
            className="g1-input"
            type="text"
            inputMode="url"
            autoComplete="off"
            spellCheck={false}
            placeholder={t('send.placeholder')}
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            required
          />
        </div>
        <div className="flex flex-wrap gap-3">
          <button type="submit" className="g1-btn g1-btn--primary" disabled={!url.trim() || create.isPending}>
            {create.isPending ? t('send.making') : t('send.make')}
          </button>
        </div>
        {duplicate && (
          <Callout tone="info" title={t('send.duplicateTitle', { date: formatDate(duplicate.book.created_at, lang) })}>
            {t('send.duplicateText')}
            <div className="mt-3 flex flex-wrap gap-2">
              {duplicate.book.can_download && (
                <Link className="g1-btn g1-btn--sm" to={`/books/${duplicate.book.id}`}>
                  {t('send.openIt')}
                </Link>
              )}
              <button
                type="button"
                className="g1-btn g1-btn--sm"
                disabled={create.isPending}
                onClick={() => create.mutate({ link: duplicate.url, force: true })}
              >
                {t('send.sendAgain')}
              </button>
            </div>
          </Callout>
        )}
        <ErrorCallout code={code} />
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
    </div>
  );
}
