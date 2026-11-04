export type Provider = 'telegram' | 'google' | 'email';
export type Target = 'kindle' | 'download';
export type BookStatus = 'processing' | 'ready' | 'sent' | 'preview' | 'failed' | 'interrupted';
export type Stage = 'received' | 'queued' | 'fetching' | 'building' | 'sending';
export type Failure = 'blocked' | 'extract' | 'fetch' | 'email' | 'unknown';

export interface Me {
  name: string | null;
  email: string | null;
  kindle_email: string | null;
  setup_verified: boolean;
  image_links: boolean;
  language: 'en' | 'de' | null;
  sender_email: string | null;
  amazon_settings_url: string;
  providers: Provider[];
}

export interface SessionInfo {
  user: Me | null;
  providers: Record<Provider, boolean>;
  /** Whether problems with a book can be reported to the admin */
  feedback: boolean;
}

export interface Book {
  id: number;
  url: string;
  host: string;
  title: string;
  status: BookStatus;
  stage: Stage | null;
  delivered: Target[];
  failure: Failure | null;
  detail: string | null;
  created_at: string | null;
  size: number | null;
  minutes: number | null;
  /** Only the free part of a paywalled post is in the book */
  paywalled: boolean;
  can_download: boolean;
}

export const FEEDBACK_REASONS = ['text', 'images', 'layout', 'wrong', 'other'] as const;
export type FeedbackReason = (typeof FEEDBACK_REASONS)[number];
export const FEEDBACK_MAX = 1000;

export class ApiError extends Error {
  constructor(
    public code: string,
    public status: number,
    public extra: Record<string, unknown> = {},
  ) {
    super(code);
  }
}

/** The API error code behind whatever a request threw, or null when nothing went wrong. */
export function errorCode(error: unknown): string | null {
  if (!error) return null;
  return error instanceof ApiError ? error.code : 'UNKNOWN';
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      method,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError('NETWORK', 0);
  }
  if (response.status === 204) return undefined as T;
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const { code, ...extra } = (data?.error ?? {}) as { code?: string };
    throw new ApiError(code ?? 'UNKNOWN', response.status, extra);
  }
  return data as T;
}

export const getSession = () => request<SessionInfo>('GET', '/api/session');
export const updateMe = (body: { kindle_email?: string; image_links?: boolean; language?: string }) =>
  request<{ user: Me }>('PATCH', '/api/me', body);
export const deleteMe = () => request<void>('DELETE', '/api/me');
export const sendTestBook = () => request<void>('POST', '/api/me/test-book');
export const confirmSetup = () => request<{ user: Me }>('POST', '/api/me/setup-verified');
export const signOut = () => request<void>('POST', '/api/auth/signout');

export const startEmailSignIn = (email: string, lang: string) =>
  request<void>('POST', '/api/auth/email/start', { email, lang });
export const verifyEmailCode = (email: string, code: string) =>
  request<{ user: Me }>('POST', '/api/auth/email/verify', { email, code });
export const verifyEmailToken = (token: string) => request<{ user: Me }>('POST', '/api/auth/email/verify', { token });

export const listBooks = (offset = 0, limit = 20) =>
  request<{ books: Book[]; total: number }>('GET', `/api/books?offset=${offset}&limit=${limit}`);
export const getBook = (id: number) => request<{ book: Book }>('GET', `/api/books/${id}`);
/** Builds the book without delivering it, so it can be looked at first. */
export const createBook = (url: string, force = false) => request<{ book: Book }>('POST', '/api/books', { url, force });
/** Delivers a built book; with no target, builds it again (a retry after a failure). */
export const resendBook = (id: number, target?: Target) =>
  request<{ book: Book }>('POST', `/api/books/${id}/send`, target ? { target } : {});
export const sendFeedback = (id: number, reasons: FeedbackReason[], message: string) =>
  request<void>('POST', `/api/books/${id}/feedback`, { reasons, message });

export const downloadUrl = (id: number) => `/api/books/${id}/epub`;
export const previewUrl = (id: number) => `/api/books/${id}/preview`;
export const signInUrl = (provider: 'telegram' | 'google', next = '/') =>
  `/api/auth/${provider}/start?next=${encodeURIComponent(next)}`;
