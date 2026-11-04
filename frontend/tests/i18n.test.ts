import { describe, expect, it } from 'vitest';
import { de } from '../src/client/i18n/de';
import { en } from '../src/client/i18n/en';
import { asLang, format, lookup } from '../src/client/i18n';
import { formatSize, safeNext } from '../src/client/lib/format';

function flatten(node: unknown, prefix = ''): Record<string, string> {
  return Object.entries(node as Record<string, unknown>).reduce<Record<string, string>>((all, [key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    return typeof value === 'string' ? { ...all, [path]: value } : { ...all, ...flatten(value, path) };
  }, {});
}

const placeholders = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map((match) => match[1]).sort();
const english = flatten(en);
const german = flatten(de);

describe('translations', () => {
  it('German has exactly the keys English has', () => {
    expect(Object.keys(german).sort()).toEqual(Object.keys(english).sort());
  });

  it('uses the same placeholders in every language', () => {
    for (const [key, text] of Object.entries(english)) {
      expect(placeholders(german[key]), key).toEqual(placeholders(text));
    }
  });

  it('has no empty texts', () => {
    for (const [key, text] of [...Object.entries(english), ...Object.entries(german)]) {
      expect(text.trim(), key).not.toBe('');
    }
  });

  it('follows the voice rules: no exclamation marks, no "please", no "successfully"', () => {
    for (const [key, text] of Object.entries(english)) {
      expect(text, key).not.toMatch(/!|\bplease\b|\bsuccessfully\b|click here/i);
    }
    for (const [key, text] of Object.entries(german)) {
      expect(text, key).not.toMatch(/!|\bbitte\b|\berfolgreich\b/i);
    }
  });

  it('has a message for every error code the API and the sign-in redirect can send', () => {
    const codes = [
      'NETWORK', 'UNKNOWN', 'UNAUTHENTICATED', 'FORBIDDEN', 'NOT_FOUND', 'INVALID_REQUEST', 'INVALID_EMAIL',
      'INVALID_URL', 'INVALID_TARGET', 'INVALID_LANGUAGE', 'INVALID_KINDLE_EMAIL', 'NO_KINDLE', 'RATE_LIMITED',
      'WRONG_CODE', 'EXPIRED', 'TOO_MANY_ATTEMPTS', 'EMAIL_FAILED', 'LINK_CONFLICT', 'ALREADY_RUNNING',
      'FILE_GONE', 'ACCESS_DENIED', 'SESSION_EXPIRED', 'PROVIDER_ERROR', 'PROVIDER_UNAVAILABLE',
      'INVALID_TOKEN', 'EMAIL_UNVERIFIED',
    ];
    for (const code of codes) expect(english[`errors.${code}`], code).toBeTruthy();
  });
});

describe('helpers', () => {
  it('fills placeholders and leaves unknown ones visible', () => {
    expect(format('Hi {name}, {n} left', { name: 'Ann', n: 3 })).toBe('Hi Ann, 3 left');
    expect(format('Hi {name}', {})).toBe('Hi {name}');
    expect(format('No placeholders')).toBe('No placeholders');
  });

  it('looks messages up by path', () => {
    expect(lookup(en, 'home.steps.paste.title')).toBe('Paste a link');
    expect(lookup(en, 'home.steps')).toBeUndefined();
    expect(lookup(en, 'nope.nothing')).toBeUndefined();
  });

  it('understands language tags', () => {
    expect(asLang('de-AT')).toBe('de');
    expect(asLang('EN-gb')).toBe('en');
    expect(asLang('fr')).toBeNull();
    expect(asLang(null)).toBeNull();
  });

  it('only sends people to places on this site after signing in', () => {
    expect(safeNext('/settings?error=x')).toBe('/settings?error=x');
    for (const bad of ['//evil.example', 'https://evil.example', '/\\evil.example', '', null]) {
      expect(safeNext(bad), String(bad)).toBe('/');
    }
  });

  it('formats sizes like the bot does', () => {
    expect(formatSize(1000, 'en')).toBe('1 KB');
    expect(formatSize(1_572_864, 'en')).toBe('1.5 MB');
    expect(formatSize(1_572_864, 'de')).toBe('1,5 MB');
    expect(formatSize(null, 'en')).toBe('');
  });
});
