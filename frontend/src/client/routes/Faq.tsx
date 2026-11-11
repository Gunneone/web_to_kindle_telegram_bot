import { useEffect } from 'react';
import { useLocation } from 'react-router';
import { FaqList, RichText, type Question } from '../components/Faq';
import { PageHead } from '../components/Text';
import { useT } from '../i18n';
import { usePageTitle } from '../lib/title';

const GROUPS: Record<'basics' | 'reader' | 'articles' | 'account', readonly Question[]> = {
  basics: ['free', 'account', 'devices', 'who'],
  reader: ['sender', 'notArriving', 'pocketbook', 'otherReaders', 'images'],
  articles: ['sites', 'paywall', 'wrong', 'several', 'shortcuts'],
  account: ['bot', 'emptyLibrary', 'keep', 'data', 'delete'],
};

/** Every question, grouped. `/faq#not-arriving` opens that one and scrolls to it. */
export function Faq() {
  const t = useT();
  usePageTitle(t('faq.title'));
  const { hash } = useLocation();

  useEffect(() => {
    const target = hash ? document.getElementById(decodeURIComponent(hash.slice(1))) : null;
    if (!(target instanceof HTMLDetailsElement)) return;
    target.open = true;
    target.scrollIntoView({ block: 'start' });
  }, [hash]);

  return (
    <div className="g1-container esel-column">
      <PageHead eyebrow={t('faq.eyebrow')} title={t('faq.title')} scribble={t('faq.scribble')} lead={t('faq.lead')} />
      {(Object.keys(GROUPS) as (keyof typeof GROUPS)[]).map((group) => (
        <section key={group} className="esel-faq-group" aria-labelledby={`faq-${group}`}>
          <h2 id={`faq-${group}`} className="esel-faq-group__title">
            {t(`faq.groups.${group}`)}
          </h2>
          <FaqList questions={GROUPS[group]} />
        </section>
      ))}
      <section className="esel-faq-group">
        <h2 className="esel-faq-group__title">{t('faq.more.title')}</h2>
        <p className="m-0 max-w-prose text-muted">
          <RichText text={t('faq.more.text')} />
        </p>
      </section>
    </div>
  );
}
