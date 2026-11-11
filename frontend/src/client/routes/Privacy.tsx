import { PageHead } from '../components/Text';
import { useT } from '../i18n';
import { usePageTitle } from '../lib/title';

const SECTIONS = ['what', 'books', 'mail', 'cookies', 'third', 'delete'] as const;

export function Privacy() {
  const t = useT();
  usePageTitle(t('privacy.title'));
  return (
    <div className="g1-container esel-column">
      <PageHead eyebrow={t('privacy.eyebrow')} title={t('privacy.title')} lead={t('privacy.lead')} />
      <p className="g1-meta">
        last_updated <span className="g1-hl">=</span> {t('privacy.updated')}
      </p>
      <div className="g1-prose">
        {SECTIONS.map((section) => (
          <section key={section}>
            <h2>{t(`privacy.sections.${section}.title`)}</h2>
            <p>{t(`privacy.sections.${section}.text`)}</p>
          </section>
        ))}
      </div>
    </div>
  );
}
