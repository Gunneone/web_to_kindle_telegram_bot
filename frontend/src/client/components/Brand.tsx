import { Link } from 'react-router';
import { useT } from '../i18n';

/** The shared header's brand: Eselsohr's mark and name. */
export function Brand() {
  const t = useT();
  return (
    <Link to="/" className="g1-brand">
      <img className="g1-brand__mark" src="/eselsohr-mark.svg" alt="" width={28} height={28} />
      <span>{t('common.appName')}</span>
    </Link>
  );
}
