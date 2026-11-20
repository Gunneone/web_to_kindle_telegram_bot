import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { useSession } from '../lib/session';
import { updateMe } from '../lib/api';
import { de } from './de';
import { en } from './en';

export type Lang = 'en' | 'de';
export const LANGS: readonly Lang[] = ['en', 'de'];
/** Each language in its own words, so people find theirs whatever language the page is in. */
export const LANGUAGE_NAMES: Record<Lang, string> = { en: 'English', de: 'Deutsch' };

type DeepStrings<T> = { [K in keyof T]: T[K] extends string ? string : DeepStrings<T[K]> };
/** The shape every language must have: the keys of `en.ts`, with any text as value. */
export type Messages = DeepStrings<typeof en>;

type Leaves<T, P extends string = ''> = {
  [K in keyof T & string]: T[K] extends string ? `${P}${K}` : Leaves<T[K], `${P}${K}.`>;
}[keyof T & string];
export type MessageKey = Leaves<typeof en>;

const CATALOGS: Record<Lang, Messages> = { en, de };
const STORAGE_KEY = 'eselsohr.lang';

export function format(template: string, vars?: Record<string, string | number>): string {
  return vars ? template.replace(/\{(\w+)\}/g, (match, name: string) => String(vars[name] ?? match)) : template;
}

export function lookup(messages: Messages, key: string): string | undefined {
  let node: unknown = messages;
  for (const part of key.split('.')) {
    if (typeof node !== 'object' || node === null) return undefined;
    node = (node as Record<string, unknown>)[part];
  }
  return typeof node === 'string' ? node : undefined;
}

export function asLang(value: string | null | undefined): Lang | null {
  const code = (value ?? '').toLowerCase().split('-')[0];
  return (LANGS as readonly string[]).includes(code) ? (code as Lang) : null;
}

function stored(): Lang | null {
  try {
    return asLang(localStorage.getItem(STORAGE_KEY));
  } catch {
    return null;
  }
}

interface I18n {
  lang: Lang;
  /** Resolves once the account has stored it (at once when signed out); rejects if that failed. */
  setLang: (lang: Lang) => Promise<void>;
  t: (key: MessageKey, vars?: Record<string, string | number>) => string;
  /** Text for a code like `RATE_LIMITED` from the API or the sign-in redirect, with a safe fallback. */
  error: (code: string | undefined | null) => string;
}

const Context = createContext<I18n | null>(null);

/** Language: the account's choice, else the one picked on this device, else the browser's, else English. */
export function I18nProvider({ children }: { children: ReactNode }) {
  const session = useSession();
  const [local, setLocal] = useState<Lang | null>(stored);
  const lang = asLang(session.data?.user?.language) ?? local ?? asLang(navigator.language) ?? 'en';

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = useCallback(
    (next: Lang) => {
      setLocal(next);
      try {
        localStorage.setItem(STORAGE_KEY, next);
      } catch {
        /* private mode: the choice lasts until the page closes */
      }
      if (!session.data?.user) return Promise.resolve();
      return updateMe({ language: next }).then(() => void session.refetch());
    },
    [session],
  );

  const value = useMemo<I18n>(() => {
    const messages = CATALOGS[lang];
    const t = (key: MessageKey, vars?: Record<string, string | number>) =>
      format(lookup(messages, key) ?? lookup(en, key) ?? key, vars);
    const error = (code: string | undefined | null) =>
      lookup(messages, `errors.${code}`) ?? lookup(messages, 'errors.UNKNOWN') ?? 'Error';
    return { lang, setLang, t, error };
  }, [lang, setLang]);

  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useI18n(): I18n {
  const value = useContext(Context);
  if (!value) throw new Error('useI18n needs an I18nProvider');
  return value;
}

export function useT() {
  return useI18n().t;
}
