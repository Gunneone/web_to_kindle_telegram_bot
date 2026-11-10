import { IconArrowRight } from '@tabler/icons-react';
import { Link } from 'react-router';
import { PageHead } from '../components/Text';
import { useT } from '../i18n';
import { usePageTitle } from '../lib/title';

export function NotFound() {
  const t = useT();
  usePageTitle(t('titles.notFound'));
  return (
    <div className="g1-container">
      <PageHead eyebrow={t('notFound.eyebrow')} title={t('notFound.title')} scribble={t('notFound.scribble')} lead={t('notFound.lead')} />
      <Link to="/" className="g1-btn g1-btn--primary">
        {t('notFound.home')} <IconArrowRight className="g1-icon g1-arrow" aria-hidden />
      </Link>
    </div>
  );
}
