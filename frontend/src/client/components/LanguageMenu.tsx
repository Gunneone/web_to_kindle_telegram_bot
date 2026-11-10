import { IconCheck, IconLanguage } from '@tabler/icons-react';
import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';
import { LANGS, LANGUAGE_NAMES, useI18n, type Lang } from '../i18n';

/** The header's language picker: an icon button that opens a menu with one entry per language. */
export function LanguageMenu() {
  const { t, lang, setLang } = useI18n();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const items = useRef<(HTMLButtonElement | null)[]>([]);
  const menuId = useId();

  // Opening puts focus on the current language, so arrow keys start from there.
  useEffect(() => {
    if (open) items.current[LANGS.indexOf(lang)]?.focus();
  }, [open, lang]);

  // A click anywhere else closes the menu.
  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', onPointerDown);
    return () => document.removeEventListener('pointerdown', onPointerDown);
  }, [open]);

  const close = () => {
    setOpen(false);
    button.current?.focus();
  };

  const choose = (code: Lang) => {
    if (code !== lang) setLang(code).catch(() => undefined); // the page switches either way
    close();
  };

  const onButtonKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      setOpen(true);
    }
  };

  const onMenuKeyDown = (event: KeyboardEvent) => {
    const current = items.current.indexOf(document.activeElement as HTMLButtonElement);
    const last = LANGS.length - 1;
    const next = {
      ArrowDown: current < last ? current + 1 : 0,
      ArrowUp: current > 0 ? current - 1 : last,
      Home: 0,
      End: last,
    }[event.key];
    if (next !== undefined) {
      event.preventDefault();
      items.current[next]?.focus();
    } else if (event.key === 'Escape') {
      event.preventDefault();
      close();
    } else if (event.key === 'Tab') {
      setOpen(false);
    }
  };

  return (
    <div ref={root} className="relative">
      <button
        ref={button}
        type="button"
        className="g1-btn g1-btn--ghost g1-btn--icon"
        aria-label={t('common.language')}
        title={t('common.language')}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onClick={() => setOpen((value) => !value)}
        onKeyDown={onButtonKeyDown}
      >
        <IconLanguage className="g1-icon" aria-hidden />
      </button>
      {open && (
        <div id={menuId} role="menu" aria-label={t('common.language')} className="g1-chamfer esel-menu" onKeyDown={onMenuKeyDown}>
          {LANGS.map((code, index) => (
            <button
              key={code}
              ref={(element) => {
                items.current[index] = element;
              }}
              type="button"
              role="menuitemradio"
              aria-checked={code === lang}
              lang={code}
              tabIndex={-1}
              className="esel-menu__item"
              onClick={() => choose(code)}
            >
              {LANGUAGE_NAMES[code]}
              {code === lang && <IconCheck className="g1-icon esel-menu__check" aria-hidden />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
