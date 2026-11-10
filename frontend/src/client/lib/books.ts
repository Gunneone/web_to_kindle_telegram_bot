import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query';
import { getBook, listBooks, type Book, type HistoryShow } from './api';
import { useMe } from './session';

const POLL_MS = 1200;
/** Books sent to a Kindle up to this many point to help in case one never arrives. */
const HINT_BOOKS = 5;

const working = (books: Book[] | undefined) => books?.some((book) => book.status === 'processing') ?? false;

/** Where a book stands: still being made, where it went, or what went wrong. Paywalled is a separate tag. */
export type Place = 'processing' | 'kindle' | 'telegram' | 'sent' | 'notSent' | 'failed' | 'interrupted';

export function placeOf(book: Book): Place {
  if (book.status === 'processing' || book.status === 'failed' || book.status === 'interrupted') return book.status;
  if (book.delivered.includes('kindle')) return 'kindle';
  if (book.delivered.includes('telegram')) return 'telegram';
  // Old rows only say that they were sent, not where
  if (book.status === 'sent' || book.status === 'preview') return 'sent';
  return 'notSent';
}

/**
 * Whether to point to "not on your Kindle?" in lists: "sent" only means the mail went out, and Amazon drops
 * mail from senders it doesn't know without a word. Worth saying for the first few books, and until a
 * test book has arrived. The book page always offers it.
 */
export function useArrivalHint(): boolean {
  const me = useMe();
  return Boolean(me && (!me.setup_verified || me.kindle_books <= HINT_BOOKS));
}

/** The latest few books; refreshes while one is being made. */
export function useRecentBooks() {
  return useQuery({
    queryKey: ['books', 'recent'],
    queryFn: () => listBooks(0, 5),
    refetchInterval: (query) => (working(query.state.data?.books) ? POLL_MS : false),
  });
}

/** Every book (or those matching a search and filter), a page at a time; refreshes while one is being made. */
export function useAllBooks(search = '', show: HistoryShow | '' = '') {
  return useInfiniteQuery({
    queryKey: ['books', 'all', search, show],
    initialPageParam: 0,
    queryFn: ({ pageParam }) => listBooks(pageParam, 20, search, show),
    getNextPageParam: (last, pages) => {
      const loaded = pages.reduce((count, page) => count + page.books.length, 0);
      return loaded < last.total ? loaded : undefined;
    },
    placeholderData: (previous) => previous, // keep the list on screen while a new search loads
    refetchInterval: (query) => (working(query.state.data?.pages.flatMap((page) => page.books)) ? POLL_MS : false),
  });
}

/** One book; refreshes while it is being made or sent. */
export function useBook(id: number) {
  return useQuery({
    queryKey: ['books', 'one', id],
    queryFn: () => getBook(id),
    enabled: Number.isInteger(id) && id > 0,
    refetchInterval: (query) => (working(query.state.data ? [query.state.data.book] : undefined) ? POLL_MS : false),
  });
}

export function useRefreshBooks() {
  const client = useQueryClient();
  return () => client.invalidateQueries({ queryKey: ['books'] });
}
