import { IconCheck } from '@tabler/icons-react';
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { useI18n } from '../i18n';

/** A confirmation that shows for a moment: `flash()` after something was saved. */
export function useSavedFlash(ms = 2500): [boolean, () => void] {
  const [shown, setShown] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  useEffect(() => () => clearTimeout(timer.current), []);
  const flash = useCallback(() => {
    clearTimeout(timer.current);
    setShown(true);
    timer.current = setTimeout(() => setShown(false), ms);
  }, [ms]);
  return [shown, flash];
}

/**
 * "✓ Saved", the one way every setting confirms it was stored, whether it saves on change or on a button.
 * The live region stays in the page, so screen readers hear each confirmation.
 */
export function Saved({ show, children }: { show: boolean; children?: ReactNode }) {
  const { t } = useI18n();
  return (
    <span role="status" className="inline-flex min-h-5 items-center gap-1 text-sm text-success">
      {show && (
        <>
          <IconCheck className="g1-icon" aria-hidden />
          {children ?? t('common.saved')}
        </>
      )}
    </span>
  );
}
