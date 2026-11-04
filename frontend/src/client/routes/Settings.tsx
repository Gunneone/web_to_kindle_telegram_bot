import { useMutation, useQueryClient } from '@tanstack/react-query';
import { IconArrowUpRight, IconCopy } from '@tabler/icons-react';
import { useState, type FormEvent } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { Callout, ErrorCallout } from '../components/Callout';
import { EmailSignIn } from '../components/EmailSignIn';
import { PageHead, SectionHead } from '../components/Text';
import { LANGS, useI18n, type Lang } from '../i18n';
import {
  confirmSetup,
  deleteMe,
  sendTestBook,
  signInUrl,
  signOut,
  updateMe,
  type ApiError,
  type Me,
  type Provider,
} from '../lib/api';
import { useMe, useResetSession, useSession, useSetUser } from '../lib/session';

const LANGUAGE_NAMES: Record<Lang, string> = { en: 'English', de: 'Deutsch' };

function KindleSection({ me }: { me: Me }) {
  const { t } = useI18n();
  const setUser = useSetUser();
  const [address, setAddress] = useState(me.kindle_email ?? '');
  const [copied, setCopied] = useState(false);
  const [testSent, setTestSent] = useState(false);

  const save = useMutation({
    mutationFn: (value: string) => updateMe({ kindle_email: value }),
    onSuccess: ({ user }) => {
      setUser(user);
      setAddress(user.kindle_email ?? '');
      setTestSent(false);
    },
  });
  const test = useMutation({ mutationFn: sendTestBook, onSuccess: () => setTestSent(true) });
  const arrived = useMutation({ mutationFn: confirmSetup, onSuccess: ({ user }) => setUser(user) });
  const error = (save.error ?? test.error ?? arrived.error) as ApiError | null;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate(address.trim());
  };
  const copy = async () => {
    if (!me.sender_email) return;
    try {
      await navigator.clipboard.writeText(me.sender_email);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard blocked: the address is selectable on screen */
    }
  };

  return (
    <section className="g1-section">
      <SectionHead eyebrow={t('settings.kindle.eyebrow')} title={t('settings.kindle.title')} />
      <div className="g1-stack">
        {me.setup_verified && me.kindle_email && <Callout tone="success">{t('settings.kindle.connected')}</Callout>}
        <p className="m-0 text-muted">{t('settings.kindle.step1')}</p>
        <form onSubmit={submit} className="g1-stack">
          <div>
            <label className="g1-label" htmlFor="kindle-address">
              {t('settings.kindle.addressLabel')}
            </label>
            <input
              id="kindle-address"
              className="g1-input"
              type="email"
              autoComplete="off"
              placeholder={t('settings.kindle.addressPlaceholder')}
              value={address}
              onChange={(event) => setAddress(event.target.value)}
            />
          </div>
          <div>
            <button type="submit" className="g1-btn" disabled={save.isPending || address.trim() === (me.kindle_email ?? '')}>
              {save.isSuccess && address.trim() === (me.kindle_email ?? '') ? t('common.saved') : t('common.save')}
            </button>
          </div>
        </form>

        {me.kindle_email && (
          <>
            <p className="m-0 text-muted">{t('settings.kindle.step2')}</p>
            {me.sender_email ? (
              <div className="flex flex-wrap items-center gap-2">
                <code className="g1-mono select-all bg-surface-2 px-3 py-2">{me.sender_email}</code>
                <button type="button" className="g1-btn g1-btn--sm" onClick={() => void copy()}>
                  <IconCopy className="g1-icon" aria-hidden />
                  {copied ? t('common.copied') : t('common.copy')}
                </button>
                <a className="g1-link inline-flex items-center gap-1" href={me.amazon_settings_url} target="_blank" rel="noopener noreferrer">
                  {t('settings.kindle.amazonLink')} <IconArrowUpRight className="g1-icon" aria-hidden />
                </a>
              </div>
            ) : (
              <Callout tone="warning">{t('settings.kindle.noSender')}</Callout>
            )}

            <p className="m-0 text-muted">{t('settings.kindle.step3')}</p>
            <div className="flex flex-wrap gap-2">
              <button type="button" className="g1-btn" disabled={test.isPending} onClick={() => test.mutate()}>
                {t('settings.kindle.testBook')}
              </button>
              {testSent && !me.setup_verified && (
                <button type="button" className="g1-btn g1-btn--primary" disabled={arrived.isPending} onClick={() => arrived.mutate()}>
                  {t('settings.kindle.arrived')}
                </button>
              )}
            </div>
            {testSent && !me.setup_verified && (
              <Callout tone="info">
                {t('settings.kindle.testSent', { email: me.kindle_email ?? '' })} {t('settings.kindle.notArrived')}
              </Callout>
            )}
          </>
        )}
        <ErrorCallout code={error?.code} />
      </div>
    </section>
  );
}

function BooksSection({ me }: { me: Me }) {
  const { t, lang, setLang } = useI18n();
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
        <div>
          <label className="g1-label" htmlFor="language">
            {t('settings.books.language')}
          </label>
          <select id="language" className="g1-select" value={lang} onChange={(event) => setLang(event.target.value as Lang)}>
            {LANGS.map((code) => (
              <option key={code} value={code}>
                {LANGUAGE_NAMES[code]}
              </option>
            ))}
          </select>
        </div>
      </div>
    </section>
  );
}

function AccountSection({ me }: { me: Me }) {
  const { t } = useI18n();
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
