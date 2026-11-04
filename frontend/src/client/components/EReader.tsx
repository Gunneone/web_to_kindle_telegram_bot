import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useI18n } from '../i18n';

const WORDS_PER_MINUTE = 230; // as the server counts reading time

interface Position {
  percent: number;
  minutesLeft: number | null;
}

/**
 * A small Kindle-like e-reader with the book on its screen, scrollable like a long page, and the
 * Kindle reading footer (time left, how far in) underneath. The book comes from the server as one
 * self-contained page in a sandboxed frame: no scripts, nothing loaded from elsewhere, links open
 * in a new tab. Without `src` the screen shows `children` instead (progress, or what went wrong).
 */
export function EReader({ src, title, children }: { src?: string; title: string; children?: ReactNode }) {
  const { t } = useI18n();
  const frame = useRef<HTMLIFrameElement>(null);
  const [loaded, setLoaded] = useState(false);
  const [position, setPosition] = useState<Position | null>(null);
  useEffect(() => {
    setLoaded(false);
    setPosition(null);
  }, [src]);

  // The frame is same-origin (and runs no scripts of its own), so the footer can follow its scrolling
  useEffect(() => {
    const win = loaded ? frame.current?.contentWindow : null;
    const doc = win?.document;
    if (!win || !doc?.body) return;
    const words = (doc.body.innerText || '').split(/\s+/).filter(Boolean).length;
    const update = () => {
      const max = doc.documentElement.scrollHeight - win.innerHeight;
      const done = max > 0 ? Math.min(1, Math.max(0, win.scrollY / max)) : 1;
      setPosition({
        percent: Math.round(done * 100),
        minutesLeft: words > 0 ? Math.max(0, Math.ceil(((1 - done) * words) / WORDS_PER_MINUTE)) : null,
      });
    };
    update();
    win.addEventListener('scroll', update, { passive: true });
    win.addEventListener('resize', update);
    return () => {
      win.removeEventListener('scroll', update);
      win.removeEventListener('resize', update);
    };
  }, [loaded]);

  return (
    <figure className="esel-reader">
      <div className="esel-reader__screen">
        {src ? (
          <>
            <iframe
              ref={frame}
              key={src}
              src={src}
              title={title}
              // No allow-scripts, so allow-same-origin is safe (the page's CSP forbids scripts as well);
              // some browsers refuse to load opaque-origin frames at all
              sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox"
              referrerPolicy="no-referrer"
              onLoad={() => setLoaded(true)}
            />
            <div className="esel-reader__footer" aria-hidden>
              <span>
                {position?.minutesLeft != null &&
                  (position.minutesLeft > 0 ? t('book.minutesLeft', { n: position.minutesLeft }) : t('book.end'))}
              </span>
              <span>{position && t('book.percent', { n: position.percent })}</span>
            </div>
            {!loaded && (
              <div className="esel-reader__status" role="status">
                {t('book.readerLoading')}
              </div>
            )}
          </>
        ) : (
          <div className="esel-reader__status">{children}</div>
        )}
      </div>
      <figcaption className="esel-reader__brand" aria-hidden>
        {t('common.appName')}
      </figcaption>
    </figure>
  );
}
