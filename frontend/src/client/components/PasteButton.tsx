import { IconClipboard } from '@tabler/icons-react';
import { useI18n } from '../i18n';

const canRead = typeof navigator !== 'undefined' && typeof navigator.clipboard?.readText === 'function';

/** Fills a link field from the clipboard: one tap on a phone instead of long-press, paste. */
export function PasteButton({ onPaste }: { onPaste: (text: string) => void }) {
  const { t } = useI18n();
  if (!canRead) return null;
  const paste = async () => {
    try {
      const text = (await navigator.clipboard.readText()).trim();
      if (text) onPaste(text);
    } catch {
      /* the browser said no: pasting by hand still works */
    }
  };
  return (
    <button type="button" className="g1-btn shrink-0" onClick={() => void paste()}>
      <IconClipboard className="g1-icon" aria-hidden />
      <span className="max-sm:sr-only">{t('send.paste')}</span>
    </button>
  );
}
