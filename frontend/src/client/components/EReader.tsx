import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useI18n } from '../i18n';

const WORDS_PER_MINUTE = 230; // as the server counts reading time

/**
 * Lays the book out in pages, like a Kindle: one column per screen, side by side, and turning a page
 * moves the body one screen width to the left. The body's padding (16px, as in the book's own style)
 * is half a gap on either side of every page, so a page is exactly one screen wide.
 */
const PAGED_CSS = `
html { height: 100%; overflow: hidden; touch-action: pan-y pinch-zoom; overscroll-behavior: none; }
body {
  box-sizing: border-box; height: 100%; margin: 0; padding: 16px;
  column-width: calc(100vw - 32px); column-gap: 32px; column-fill: auto;
}
h1, h2, h3, h4, h5, h6 { break-after: avoid; }
img, svg, video, figure, pre, table, li { break-inside: avoid; }
img, svg, video { max-height: calc(100vh - 48px) !important; object-fit: contain; }
hr.eselsohr-break { break-after: column; border: 0; margin: 0; }
`;

/** How far a finger has to move sideways for a swipe, in CSS pixels */
const SWIPE = 40;

interface Position {
  percent: number;
  minutesLeft: number | null;
}

/**
 * A small Kindle-like e-reader with the book on its screen in pages, and the Kindle reading footer
 * (time left, how far in) underneath. Tap or click the right side (or swipe, use the arrow keys or the
 * mouse wheel) to turn the page; the left third goes back. The book comes from the server as one
 * self-contained page in a sandboxed frame: no scripts, nothing loaded from elsewhere, links open in a
 * new tab. Without `src` the screen shows `children` instead (progress, or what went wrong).
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

  // The frame is same-origin and runs no scripts of its own, so the reader lays it out in pages and
  // listens to it from here (the listeners run in this page)
  useEffect(() => {
    const win = loaded ? frame.current?.contentWindow : null;
    let doc: Document | undefined;
    try {
      doc = win?.document;
    } catch {
      return; // the preview failed and the browser put its own (cross-origin) error page in the frame
    }
    if (!win || !doc?.body) return;
    const style = doc.createElement('style');
    style.textContent = PAGED_CSS;
    doc.head.append(style);
    const root = doc.scrollingElement ?? doc.documentElement;
    const body = doc.body;
    const words = (body.innerText || '').split(/\s+/).filter(Boolean).length;
    const width = () => win.innerWidth || 1;
    let page = 0;
    let pages = 1;
    // Where the text ends, counted from the first page: the last page holds that
    const count = () => {
      const range = doc.createRange();
      range.selectNodeContents(body);
      const end = range.getBoundingClientRect().right + page * width();
      return Math.max(1, Math.ceil((end - 1) / width()));
    };

    const show = (next: number) => {
      pages = count();
      page = Math.min(pages - 1, Math.max(0, next));
      body.style.transform = `translateX(${-page * width()}px)`;
      // Kindle counts what is left after this page
      const left = (words * (pages - page - 1)) / pages;
      setPosition({
        percent: Math.round(((page + 1) / pages) * 100),
        minutesLeft: words > 0 ? (left > 0 ? Math.max(1, Math.round(left / WORDS_PER_MINUTE)) : 0) : null,
      });
    };
    const turn = (by: number) => show(page + by);
    show(0);

    // Keep the place when the screen changes size (the window, or the phone turned)
    const resize = () => show(Math.floor((page / pages) * count()));
    // The browser scrolled the frame to show something on another page (tabbing to a link, find in
    // page): undo the scroll and turn to that page instead
    const scroll = () => {
      const x = root.scrollLeft;
      if (!x && !root.scrollTop) return;
      root.scrollLeft = 0;
      root.scrollTop = 0;
      const focused = doc.activeElement;
      const left = focused && focused !== body ? focused.getBoundingClientRect().left : x;
      show(page + Math.floor(left / width()));
    };
    const click = (event: MouseEvent) => {
      if (event.button !== 0 || (event.target as Element | null)?.closest?.('a[href]')) return;
      if (doc.getSelection()?.isCollapsed === false) return; // selecting text, not turning
      turn(event.clientX < width() / 3 ? -1 : 1);
    };
    const key = (event: KeyboardEvent) => {
      if (event.altKey || event.ctrlKey || event.metaKey) return;
      const keys: Record<string, number> = { ArrowRight: 1, PageDown: 1, ' ': event.shiftKey ? -1 : 1, ArrowLeft: -1, PageUp: -1 };
      const by = keys[event.key];
      if (!by) return;
      event.preventDefault();
      turn(by);
    };
    let start: { x: number; y: number } | null = null;
    const touchStart = (event: TouchEvent) => {
      const touch = event.touches[0];
      start = event.touches.length === 1 && touch ? { x: touch.clientX, y: touch.clientY } : null;
    };
    const touchEnd = (event: TouchEvent) => {
      const touch = event.changedTouches[0];
      if (!start || !touch) return;
      const dx = touch.clientX - start.x;
      const dy = touch.clientY - start.y;
      start = null;
      if (Math.abs(dx) > SWIPE && Math.abs(dx) > Math.abs(dy) * 1.5) {
        event.preventDefault(); // no click after a swipe
        turn(dx < 0 ? 1 : -1);
      }
    };
    // One page per wheel or trackpad gesture: turn once it has moved far enough, then ignore the rest
    // of the gesture. A trackpad keeps sending ever smaller momentum events after the fingers lift, and
    // a quick second swipe arrives before they stop, so a pause alone can't tell gestures apart. A new
    // swipe shows as the movement picking up again after it had died down (or turning around).
    let wheeled = 0;
    let turned = false;
    let peak = 0; // the biggest movement since the turn
    let valley = Infinity; // the smallest since that peak
    let settle: number | undefined;
    // The page around the reader stands still while the reader takes a gesture. Firefox (and browsers
    // built on it, like Zen) sends a trackpad gesture over a frame that can't scroll on to the page,
    // and preventDefault in the frame doesn't always stop that, so the page crept along with every
    // swipe. The page keeps room for its scrollbar (scrollbar-gutter), so nothing moves sideways.
    const outer = document.documentElement;
    let held: string | null = null; // the page's own overflow, while the reader holds it
    const hold = () => {
      if (held !== null) return;
      held = outer.style.overflow;
      outer.style.overflow = 'hidden';
    };
    const release = () => {
      if (held === null) return;
      outer.style.overflow = held;
      held = null;
    };
    const wheel = (event: WheelEvent) => {
      if (event.ctrlKey) return; // pinch to zoom
      event.preventDefault();
      hold();
      window.clearTimeout(settle);
      settle = window.setTimeout(() => {
        wheeled = 0;
        turned = false;
        release();
      }, 180);
      const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? width() : 1; // lines, pages
      const delta = (Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY) * unit;
      const size = Math.abs(delta);
      if (turned) {
        const reversed = delta !== 0 && Math.sign(delta) !== Math.sign(wheeled);
        const pickedUp = valley <= peak / 2 && size >= valley * 2 + 4;
        if (!reversed && !pickedUp) {
          if (size > peak) {
            peak = size;
            valley = Infinity;
          } else valley = Math.min(valley, size);
          return;
        }
        turned = false;
        wheeled = 0;
      }
      wheeled += delta;
      if (Math.abs(wheeled) > 40) {
        turned = true;
        peak = size;
        valley = Infinity;
        turn(wheeled > 0 ? 1 : -1);
      }
    };

    win.addEventListener('resize', resize);
    win.addEventListener('scroll', scroll, { passive: true });
    doc.addEventListener('click', click);
    doc.addEventListener('keydown', key);
    doc.addEventListener('touchstart', touchStart, { passive: true });
    doc.addEventListener('touchend', touchEnd);
    doc.addEventListener('wheel', wheel, { passive: false });
    return () => {
      window.clearTimeout(settle);
      release();
      win.removeEventListener('resize', resize);
      win.removeEventListener('scroll', scroll);
      doc.removeEventListener('click', click);
      doc.removeEventListener('keydown', key);
      doc.removeEventListener('touchstart', touchStart);
      doc.removeEventListener('touchend', touchEnd);
      doc.removeEventListener('wheel', wheel);
      style.remove();
      body.style.transform = '';
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
