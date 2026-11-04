import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query';
import { getBook, listBooks, type Book } from './api';

const POLL_MS = 1200;

const working = (books: Book[] | undefined) => books?.some((book) => book.status === 'processing') ?? false;

/** The latest few books; refreshes while one is being made. */
export function useRecentBooks() {
  return useQuery({
    queryKey: ['books', 'recent'],
    queryFn: () => listBooks(0, 5),
    refetchInterval: (query) => (working(query.state.data?.books) ? POLL_MS : false),
  });
}

/** Every book, a page at a time; refreshes while one is being made. */
export function useAllBooks() {
  return useInfiniteQuery({
    queryKey: ['books', 'all'],
    initialPageParam: 0,
    queryFn: ({ pageParam }) => listBooks(pageParam, 20),
    getNextPageParam: (last, pages) => {
      const loaded = pages.reduce((count, page) => count + page.books.length, 0);
      return loaded < last.total ? loaded : undefined;
    },
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
