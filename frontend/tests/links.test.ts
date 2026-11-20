import { describe, expect, it } from 'vitest';
import { bookmarklet, extractLinks, looksLikeLink, sharedLink } from '../src/client/lib/links';

describe('links in pasted text', () => {
  it('takes a single link as it is', () => {
    expect(extractLinks('  https://example.com/post  ')).toEqual(['https://example.com/post']);
  });

  it('finds several links, once each, in order', () => {
    const text = 'https://a.com/1 https://b.com/2\nhttps://a.com/1, and https://c.com/3.';
    expect(extractLinks(text)).toEqual(['https://a.com/1', 'https://b.com/2', 'https://c.com/3']);
  });

  it('leaves the punctuation of the sentence behind but keeps brackets of the link', () => {
    expect(extractLinks('Read this (https://example.com/post).')).toEqual(['https://example.com/post']);
    expect(extractLinks('https://en.wikipedia.org/wiki/Ear_(anatomy)')).toEqual(['https://en.wikipedia.org/wiki/Ear_(anatomy)']);
    expect(extractLinks('„https://example.com/de“')).toEqual(['https://example.com/de']);
  });

  it('passes text without a scheme on for the server to complete', () => {
    expect(extractLinks('example.com/post')).toEqual(['example.com/post']);
    expect(extractLinks('   ')).toEqual([]);
  });
});

describe('links handed over by the share sheet and the bookmarklet', () => {
  it('prefers url, then a link inside text', () => {
    expect(sharedLink(new URLSearchParams('url=https://a.com/1&text=https://b.com/2'))).toBe('https://a.com/1');
    expect(sharedLink(new URLSearchParams({ title: 'A post', text: 'A post https://b.com/2 via app' }))).toBe('https://b.com/2');
    expect(sharedLink(new URLSearchParams({ text: 'no link here' }))).toBe('');
    expect(sharedLink(new URLSearchParams())).toBe('');
  });

  it('builds a bookmarklet that opens the start page with the current address', () => {
    const code = bookmarklet('https://eselsohr.gunne.one');
    expect(code.startsWith('javascript:')).toBe(true);
    expect(code).toContain('"https://eselsohr.gunne.one/?url="');
    expect(code).toContain('encodeURIComponent(location.href)');
  });
});

describe('whether an entry could be a web address', () => {
  it('takes full links and bare addresses the server completes', () => {
    for (const entry of [
      'https://en.wikipedia.org/wiki/Dog-ear',
      'http://example.com',
      'example.com/a-long-read',
      'www.zeit.de/kultur?x=1#top',
      'https://bücher.de/lesen',
      'https://example.com:8080/post',
    ]) {
      expect(looksLikeLink(entry), entry).toBe(true);
    }
  });

  it('turns down sentences, single words and hosts without a domain', () => {
    for (const entry of ['not a url', 'hello', 'https://localhost', 'example.', 'v1.5', 'https://foo']) {
      expect(looksLikeLink(entry), entry).toBe(false);
    }
  });
});
