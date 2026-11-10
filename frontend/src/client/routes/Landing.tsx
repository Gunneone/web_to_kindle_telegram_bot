import { useMutation } from '@tanstack/react-query';
import { IconArrowRight, IconBrandTelegram } from '@tabler/icons-react';
import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router';
import { ErrorCallout } from '../components/Callout';
import { EReader } from '../components/EReader';
import { PasteButton } from '../components/PasteButton';
import { Eyebrow, PageHead, SectionHead } from '../components/Text';
import { useI18n } from '../i18n';
import { createBook, errorCode } from '../lib/api';
import { extractLinks } from '../lib/links';

const STEPS = ['paste', 'bind', 'read'] as const;
const QUESTIONS = ['free', 'devices', 'sender', 'paywall', 'data'] as const;

/**
 * What Eselsohr is, for someone who isn't signed in: try it with a link right here (the book is
 * built under a guest account, to look at and download), or flip through the sample book first.
 */
export function Landing({ initialLink = '' }: { initialLink?: string }) {
  const { t, lang } = useI18n();
  const navigate = useNavigate();
  const [url, setUrl] = useState(initialLink);
  const create = useMutation({
    mutationFn: (link: string) => createBook(link),
    onSuccess: ({ book }) => void navigate(`/books/${book.id}`),
  });

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const [link] = extractLinks(url);
    if (link) create.mutate(link);
  };
  // Signing in keeps a link that is already filled in
  const signIn = url.trim() ? `/signin?next=${encodeURIComponent(`/?url=${encodeURIComponent(url.trim())}`)}` : '/signin';

  return (
    <div className="g1-container">
      <div className="grid items-center gap-10 md:grid-cols-[minmax(0,1fr)_minmax(0,300px)]">
        <div>
          <PageHead eyebrow={t('home.eyebrow')} title={t('home.title')} scribble={t('home.scribble')} lead={t('home.lead')} />
          <form onSubmit={submit} className="g1-stack">
            <div>
              <label className="g1-label" htmlFor="try-url">
                {t('home.try.label')}
              </label>
              <div className="flex gap-2">
                <input
                  id="try-url"
                  className="g1-input min-w-0 flex-1"
                  type="text"
                  inputMode="url"
                  autoComplete="off"
                  spellCheck={false}
                  placeholder={t('home.try.placeholder')}
                  value={url}
                  onChange={(event) => setUrl(event.target.value)}
                  required
                />
                <PasteButton onPaste={setUrl} />
              </div>
            </div>
            <div className="flex flex-wrap gap-3">
              <button type="submit" className="g1-btn g1-btn--primary g1-btn--lg" disabled={!url.trim() || create.isPending}>
                {create.isPending ? t('home.try.making') : t('home.try.submit')}
                <IconArrowRight className="g1-icon g1-arrow" aria-hidden />
              </button>
              <Link to={signIn} className="g1-btn g1-btn--lg">
                {t('home.signIn')}
              </Link>
            </div>
            <p className="m-0 text-sm text-muted">{t('home.try.note')}</p>
            <ErrorCallout code={errorCode(create.error)} />
          </form>
        </div>
        <div className="flex flex-col items-center gap-3">
          <EReader src={`/sample/${lang}.html`} title={t('home.sample.title')} />
          <p className="m-0 max-w-[300px] text-center text-xs text-muted">{t('home.sample.caption')}</p>
        </div>
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

      <section className="g1-section">
        <SectionHead eyebrow={t('home.faq.eyebrow')} title={t('home.faq.title')} />
        <div className="max-w-3xl border-t border-line">
          {QUESTIONS.map((question) => (
            <details key={question} className="esel-faq border-b border-line">
              <summary>{t(`home.faq.items.${question}.q`)}</summary>
              <p className="m-0 pb-4 text-muted">{t(`home.faq.items.${question}.a`)}</p>
            </details>
          ))}
        </div>
        <div className="mt-6 flex flex-wrap gap-x-6 gap-y-3">
          <Link className="g1-link" to="/privacy">
            {t('home.faq.privacyLink')}
          </Link>
          <a className="g1-link inline-flex items-center gap-1" href="https://t.me/SubstackKindleBot" target="_blank" rel="noopener noreferrer">
            <IconBrandTelegram className="g1-icon" aria-hidden />
            {t('home.useBot')}
          </a>
        </div>
      </section>
    </div>
  );
}
