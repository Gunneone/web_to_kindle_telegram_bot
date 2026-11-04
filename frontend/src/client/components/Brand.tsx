import { Link } from 'react-router';
import { useT } from '../i18n';

/**
 * The shared header's brand: Eselsohr's mark and name. The mark has a light and a dark version with the same
 * geometry; an <img> can't see the app's data-theme attribute, so the theme picks which one is shown.
 */
export function Brand() {
  const t = useT();
  return (
    <Link to="/" className="g1-brand">
      <img className="g1-brand__mark dark:hidden" src="/eselsohr-mark.svg" alt="" width={28} height={28} />
      <img className="g1-brand__mark hidden dark:block" src="/eselsohr-mark-dark.svg" alt="" width={28} height={28} />
      <span>{t('common.appName')}</span>
    </Link>
  );
}
