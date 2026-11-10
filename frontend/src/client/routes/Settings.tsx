import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router';
import { Callout, ErrorCallout } from '../components/Callout';
import { EmailSignIn } from '../components/EmailSignIn';
import { PageHead, SectionHead } from '../components/Text';
import { LANGS, LANGUAGE_NAMES, useI18n, type Lang } from '../i18n';
import {
  deleteMe,
  signInUrl,
  signOut,
  updateMe,
  type ApiError,
  type Me,
  type Provider,
} from '../lib/api';
import { useMe, useResetSession, useSession, useSetUser } from '../lib/session';

/** The e-reader at a glance; setting it up or changing it happens in the setup (/setup). */
function KindleSection({ me }: { me: Me }) {
  const { t } = useI18n();
  return (
    <section className="g1-section">
      <SectionHead eyebrow={t('settings.kindle.eyebrow')} title={t('settings.kindle.title')} />
      {me.kindle_email ? (
        <div className="g1-stack">
          <p className="m-0 flex flex-wrap items-center gap-3">
            <code className="g1-mono break-all">{me.kindle_email}</code>
            <span className={me.setup_verified ? 'g1-badge g1-badge--primary' : 'g1-badge text-warning [--g1-edge:var(--g1-warning)]'}>
              {t(me.setup_verified ? 'settings.kindle.verified' : 'settings.kindle.unverified')}
            </span>
          </p>
          <div className="flex flex-wrap gap-2">
            <Link to="/setup?step=address" className="g1-btn g1-btn--sm">
              {t('settings.kindle.change')}
            </Link>
            <Link to="/setup" className={me.setup_verified ? 'g1-btn g1-btn--sm g1-btn--ghost' : 'g1-btn g1-btn--sm g1-btn--primary'}>
              {t('settings.kindle.openSetup')}
            </Link>
          </div>
        </div>
      ) : (
        <div className="g1-stack">
          <p className="m-0 text-muted">{t(me.download_only ? 'settings.kindle.downloadOnly' : 'settings.kindle.none')}</p>
          <div>
            <Link to={me.download_only ? '/setup?step=choose' : '/setup'} className="g1-btn g1-btn--sm g1-btn--primary">
              {t('settings.kindle.setup')}
            </Link>
          </div>
        </div>
      )}
    </section>
  );
}

function BooksSection({ me }: { me: Me }) {
  const { t } = useI18n();
  const setUser = useSetUser();
  const toggle = useMutation({
    mutationFn: (value: boolean) => updateMe({ image_links: value }),
    onSuccess: ({ user }) => setUser(user),
  });
  return (
    <section className="g1-section">
      <SectionHead eyebrow={t('settings.books.eyebrow')} title={t('settings.books.title')} />
      <div className="g1-stack">
        <label className="flex items-start gap-3">
          <input
            type="checkbox"
            className="mt-1 size-4"
            checked={toggle.isPending ? Boolean(toggle.variables) : me.image_links}
            onChange={(event) => toggle.mutate(event.target.checked)}
          />
          <span>
            {t('settings.books.imageLinks')}
            <span className="block text-sm text-muted">{t('settings.books.imageLinksHelp')}</span>
          </span>
        </label>
        <ErrorCallout code={(toggle.error as ApiError | null)?.code} />
      </div>
    </section>
  );
}

function AccountSection({ me }: { me: Me }) {
  const { t, lang, setLang } = useI18n();
  const navigate = useNavigate();
  const session = useSession();
  const reset = useResetSession();
  const client = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const [connectingEmail, setConnectingEmail] = useState(false);

  const leave = async () => {
    await reset();
    client.clear();
    navigate('/', { replace: true });
    await session.refetch();
  };
  const out = useMutation({ mutationFn: signOut, onSuccess: leave });
  const remove = useMutation({ mutationFn: deleteMe, onSuccess: leave });
  const providers = session.data?.providers;
  const connectable = (['telegram', 'google'] as const).filter((p) => providers?.[p] && !me.providers.includes(p));

  return (
    <section className="g1-section">
      <SectionHead eyebrow={t('settings.account.eyebrow')} title={t('settings.account.title')} />
      <div className="g1-stack">
        <div>
          <label className="g1-label" htmlFor="language">
            {t('settings.account.language')}
          </label>
          <select
            id="language"
            className="g1-select"
            aria-describedby="language-help"
            value={lang}
            onChange={(event) => setLang(event.target.value as Lang)}
          >
            {LANGS.map((code) => (
              <option key={code} value={code} lang={code}>
                {LANGUAGE_NAMES[code]}
              </option>
            ))}
          </select>
          <span id="language-help" className="mt-1 block text-sm text-muted">
            {t('settings.account.languageHelp')}
          </span>
        </div>
        <div>
          <div className="g1-label">{t('settings.account.signedInWith')}</div>
          <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
            {(['telegram', 'google', 'email'] as Provider[]).map((provider) =>
              me.providers.includes(provider) ? (
                <li key={provider} className="g1-badge g1-badge--primary">
                  {t(`settings.account.providers.${provider}`)}
                </li>
              ) : null,
            )}
          </ul>
        </div>
        <div className="flex flex-wrap gap-2">
          {connectable.map((provider) => (
            <a key={provider} className="g1-btn g1-btn--sm" href={signInUrl(provider, '/settings')}>
              {t('settings.account.connect')} {t(`settings.account.providers.${provider}`)}
            </a>
          ))}
          {!me.providers.includes('email') && !connectingEmail && (
            <button type="button" className="g1-btn g1-btn--sm" onClick={() => setConnectingEmail(true)}>
              {t('settings.account.connectEmail')}
            </button>
          )}
        </div>
        {connectingEmail && <EmailSignIn onDone={() => void reset().then(() => setConnectingEmail(false))} />}
        <div className="flex flex-wrap gap-2">
          <button type="button" className="g1-btn" disabled={out.isPending} onClick={() => out.mutate()}>
            {t('settings.account.signOut')}
          </button>
          {!confirming && (
            <button type="button" className="g1-btn text-danger [--g1-edge:var(--g1-danger)]" onClick={() => setConfirming(true)}>
              {t('settings.account.deleteAccount')}
            </button>
          )}
        </div>
        {confirming && (
          <Callout tone="danger" title={t('settings.account.deleteTitle')}>
            {t('settings.account.deleteText')}
            <div className="mt-3 flex gap-2">
              <button
                type="button"
                className="g1-btn g1-btn--sm text-danger [--g1-edge:var(--g1-danger)]"
                disabled={remove.isPending}
                onClick={() => remove.mutate()}
              >
                {t('settings.account.deleteConfirm')}
              </button>
              <button type="button" className="g1-btn g1-btn--sm g1-btn--ghost" onClick={() => setConfirming(false)}>
                {t('common.cancel')}
              </button>
            </div>
          </Callout>
        )}
        <ErrorCallout code={((out.error ?? remove.error) as ApiError | null)?.code} />
      </div>
    </section>
  );
}

export function Settings() {
  const { t } = useI18n();
  const me = useMe();
  const [params] = useSearchParams();
  if (!me) return null;
  return (
    <div className="g1-container">
      <PageHead eyebrow={t('settings.eyebrow')} title={t('settings.title')} />
      <ErrorCallout code={params.get('error')} />
      <KindleSection me={me} />
      <BooksSection me={me} />
      <AccountSection me={me} />
    </div>
  );
}
