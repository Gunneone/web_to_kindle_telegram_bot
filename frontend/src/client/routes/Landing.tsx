import { IconBrandTelegram } from '@tabler/icons-react';
import { Link } from 'react-router';
import { Eyebrow, PageHead, SectionHead } from '../components/Text';
import { useT } from '../i18n';

const STEPS = ['paste', 'bind', 'read'] as const;

/** What Eselsohr is, for someone who isn't signed in. */
export function Landing() {
  const t = useT();
  return (
    <div className="g1-container">
      <PageHead eyebrow={t('home.eyebrow')} title={t('home.title')} scribble={t('home.scribble')} lead={t('home.lead')} />
      <div className="flex flex-wrap gap-3">
        <Link to="/signin" className="g1-btn g1-btn--primary g1-btn--lg">
          {t('home.signIn')}
        </Link>
        <a
          href="https://t.me/SubstackKindleBot"
          className="g1-btn g1-btn--lg"
          target="_blank"
          rel="noopener noreferrer"
        >
          <IconBrandTelegram className="g1-icon" aria-hidden />
          {t('home.useBot')}
        </a>
      </div>
      <section className="g1-section">
        <SectionHead eyebrow={t('home.stepsEyebrow')} title={t('home.stepsTitle')} />
        <div className="g1-grid">
          {STEPS.map((step) => (
            <div key={step} className="g1-card">
              <Eyebrow>{t(`home.steps.${step}.eyebrow`)}</Eyebrow>
              <h3 className="g1-card__title m-0">{t(`home.steps.${step}.title`)}</h3>
              <p className="g1-card__text m-0">{t(`home.steps.${step}.text`)}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
