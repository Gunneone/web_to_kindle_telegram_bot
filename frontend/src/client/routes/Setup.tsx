import { useMutation } from '@tanstack/react-query';
import { IconArrowLeft, IconArrowRight, IconArrowUpRight, IconBook2, IconCheck, IconCopy, IconDeviceTablet, IconDownload } from '@tabler/icons-react';
import { useState, type FormEvent, type ReactNode } from 'react';
import { Link, useSearchParams } from 'react-router';
import { Callout, ErrorCallout } from '../components/Callout';
import { PageHead } from '../components/Text';
import { useI18n } from '../i18n';
import { confirmSetup, errorCode, sendTestBook, updateMe, type Me } from '../lib/api';
import { useMe, useSetUser } from '../lib/session';

type Device = 'kindle' | 'pocketbook';
type Step = 'choose' | 'address' | 'sender' | 'test' | 'done';
const NUMBERED = ['address', 'sender', 'test'] as const;

/** Where someone left off: the server remembers the address, the test book and whether it arrived. */
function firstStep(me: Me, asked: string | null): Step {
  if (asked === 'choose' || asked === 'address') return asked;
  if (!me.kindle_email) return me.download_only ? 'done' : 'choose';
  if (me.setup_verified) return 'done';
  return me.test_sent_at ? 'test' : 'sender';
}

/**
 * Setting up an e-reader, one step at a time: what do you read on, your address, approve our sender,
 * a test book. Each step survives a reload, so going off to Amazon and coming back picks up where it was.
 */
export function Setup() {
  const me = useMe();
  const [params] = useSearchParams();
  if (!me) return null;
  return <Wizard me={me} initial={firstStep(me, params.get('step'))} />;
}

function Wizard({ me, initial }: { me: Me; initial: Step }) {
  const { t } = useI18n();
  const setUser = useSetUser();
  const [step, setStep] = useState<Step>(initial);
  const [device, setDevice] = useState<Device>(me.device ?? 'kindle');
  const pocketbook = device === 'pocketbook';

  // "Something else" means no Kindle at all: the address goes, so nothing offers to send there
  const downloadOnly = useMutation({
    mutationFn: (value: boolean) => updateMe(value ? { download_only: true, kindle_email: '' } : { download_only: false }),
    onSuccess: ({ user }) => setUser(user),
  });

  const choose = (choice: Device | 'other') => {
    if (choice === 'other') {
      downloadOnly.mutate(true, { onSuccess: () => setStep('done') });
      return;
    }
    setDevice(choice);
    if (me.download_only) downloadOnly.mutate(false);
    setStep('address');
  };

  const index = (NUMBERED as readonly Step[]).indexOf(step);
  return (
    <div className="g1-container g1-container--prose">
      <PageHead eyebrow={t('setup.eyebrow')} title={t('setup.title')} lead={t('setup.lead')} />
      {index >= 0 && (
        <ol className="m-0 mb-8 flex list-none gap-2 p-0" aria-label={t('setup.stepsLabel')}>
          {NUMBERED.map((name, i) => {
            const reachable = i < index;
            const label = `${i + 1} · ${t(`setup.steps.${name}`)}`;
            return (
              <li
                key={name}
                aria-current={i === index ? 'step' : undefined}
                className={`flex-1 border-t-2 pt-2 font-mono text-xs uppercase tracking-wider ${
                  i < index ? 'border-primary text-muted' : i === index ? 'border-accent text-fg' : 'border-line text-subtle'
                }`}
              >
                {reachable ? (
                  <button type="button" className="cursor-pointer border-0 bg-transparent p-0 font-mono text-xs uppercase tracking-wider text-muted underline-offset-4 hover:underline" onClick={() => setStep(name)}>
                    {label}
                  </button>
                ) : (
                  label
                )}
              </li>
            );
          })}
        </ol>
      )}

      {step === 'choose' && <ChooseStep busy={downloadOnly.isPending} onChoose={choose} />}
      {step === 'address' && (
        <AddressStep
          me={me}
          pocketbook={pocketbook}
          onBack={() => setStep('choose')}
          onDone={() => setStep('sender')}
        />
      )}
      {step === 'sender' && <SenderStep me={me} onBack={() => setStep('address')} onDone={() => setStep('test')} />}
      {step === 'test' && <TestStep me={me} onBack={() => setStep('sender')} onFix={() => setStep('address')} onDone={() => setStep('done')} />}
      {step === 'done' && <DoneStep me={me} onChange={(next) => setStep(next)} />}
      <ErrorCallout code={errorCode(downloadOnly.error)} />
    </div>
  );
}

function StepHead({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="mb-5">
      <h2 className="m-0 text-xl">{title}</h2>
      {children && <p className="m-0 mt-2 text-muted">{children}</p>}
    </div>
  );
}

function BackButton({ onClick }: { onClick: () => void }) {
  const { t } = useI18n();
  return (
    <button type="button" className="g1-btn g1-btn--ghost" onClick={onClick}>
      <IconArrowLeft className="g1-icon" aria-hidden />
      {t('setup.back')}
    </button>
  );
}

function ChooseStep({ busy, onChoose }: { busy: boolean; onChoose: (choice: Device | 'other') => void }) {
  const { t } = useI18n();
  const options = [
    { key: 'kindle', icon: IconDeviceTablet },
    { key: 'pocketbook', icon: IconBook2 },
    { key: 'other', icon: IconDownload },
  ] as const;
  return (
    <div>
      <StepHead title={t('setup.choose.title')} />
      <div className="g1-stack">
        {options.map(({ key, icon: Icon }) => (
          <button key={key} type="button" className="g1-card esel-choice" disabled={busy} onClick={() => onChoose(key)}>
            <span className="flex items-start gap-3">
              <Icon className="g1-icon mt-1 shrink-0 text-primary" aria-hidden />
              <span>
                <span className="g1-card__title block">{t(`setup.choose.${key}.title`)}</span>
                <span className="g1-card__text block">{t(`setup.choose.${key}.text`)}</span>
              </span>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

function AddressStep({ me, pocketbook, onBack, onDone }: { me: Me; pocketbook: boolean; onBack: () => void; onDone: () => void }) {
  const { t } = useI18n();
  const setUser = useSetUser();
  const [address, setAddress] = useState(me.kindle_email ?? '');
  const save = useMutation({
    mutationFn: (value: string) => updateMe({ kindle_email: value }),
    onSuccess: ({ user }) => {
      setUser(user);
      onDone();
    },
  });
  const store = useMutation({
    mutationFn: (value: string) => updateMe({ amazon_store: value }),
    onSuccess: ({ user }) => setUser(user),
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const value = address.trim();
    if (value === me.kindle_email) onDone();
    else save.mutate(value);
  };

  return (
    <form onSubmit={submit}>
      <StepHead title={t(pocketbook ? 'setup.address.pocketbookTitle' : 'setup.address.kindleTitle')}>
        {t(pocketbook ? 'setup.address.pocketbookText' : 'setup.address.kindleText')}
      </StepHead>
      <div className="g1-stack">
        {!pocketbook && (
          <p className="m-0">
            <a className="g1-link inline-flex items-center gap-1" href={me.amazon_devices_url} target="_blank" rel="noopener noreferrer">
              {t('setup.address.findLink')} <IconArrowUpRight className="g1-icon" aria-hidden />
            </a>
          </p>
        )}
        <div>
          <label className="g1-label" htmlFor="setup-address">
            {t('setup.address.label')}
          </label>
          <input
            id="setup-address"
            className="g1-input"
            type="email"
            autoComplete="off"
            autoFocus
            placeholder={t(pocketbook ? 'setup.address.pocketbookPlaceholder' : 'setup.address.kindlePlaceholder')}
            value={address}
            onChange={(event) => setAddress(event.target.value)}
            required
          />
        </div>
        {!pocketbook && (
          <div>
            <label className="g1-label" htmlFor="setup-store">
              {t('setup.address.storeLabel')}
            </label>
            <select
              id="setup-store"
              className="g1-select"
              aria-describedby="setup-store-help"
              value={me.amazon_store}
              disabled={store.isPending}
              onChange={(event) => store.mutate(event.target.value)}
            >
              {me.amazon_stores.map((domain) => (
                <option key={domain} value={domain}>
                  {domain}
                </option>
              ))}
            </select>
            <span id="setup-store-help" className="mt-1 block text-sm text-muted">
              {t('setup.address.storeHelp')}
            </span>
          </div>
        )}
        <ErrorCallout code={errorCode(save.error ?? store.error)} />
        <div className="flex flex-wrap gap-2">
          <BackButton onClick={onBack} />
          <button type="submit" className="g1-btn g1-btn--primary" disabled={!address.trim() || save.isPending}>
            {t('setup.address.next')} <IconArrowRight className="g1-icon g1-arrow" aria-hidden />
          </button>
        </div>
      </div>
    </form>
  );
}

function SenderStep({ me, onBack, onDone }: { me: Me; onBack: () => void; onDone: () => void }) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);
  const pocketbook = me.device === 'pocketbook';
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
    <div>
      <StepHead title={t(pocketbook ? 'setup.sender.pocketbookTitle' : 'setup.sender.kindleTitle')}>
        {t(pocketbook ? 'setup.sender.pocketbookText' : 'setup.sender.kindleText')}
      </StepHead>
      <div className="g1-stack">
        {me.sender_email ? (
          <div className="flex flex-wrap items-center gap-2">
            <code className="g1-mono select-all break-all bg-surface-2 px-3 py-2">{me.sender_email}</code>
            <button type="button" className="g1-btn g1-btn--sm" onClick={() => void copy()}>
              {copied ? <IconCheck className="g1-icon" aria-hidden /> : <IconCopy className="g1-icon" aria-hidden />}
              {copied ? t('common.copied') : t('common.copy')}
            </button>
          </div>
        ) : (
          <Callout tone="warning">{t('setup.sender.noSender')}</Callout>
        )}
        {!pocketbook && (
          <p className="m-0">
            <a className="g1-link inline-flex items-center gap-1" href={me.amazon_settings_url} target="_blank" rel="noopener noreferrer">
              {t('setup.sender.amazonLink')} <IconArrowUpRight className="g1-icon" aria-hidden />
            </a>
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          <BackButton onClick={onBack} />
          <button type="button" className="g1-btn g1-btn--primary" onClick={onDone}>
            {t('setup.sender.next')} <IconArrowRight className="g1-icon g1-arrow" aria-hidden />
          </button>
        </div>
      </div>
    </div>
  );
}

function TestStep({ me, onBack, onFix, onDone }: { me: Me; onBack: () => void; onFix: () => void; onDone: () => void }) {
  const { t, lang } = useI18n();
  const setUser = useSetUser();
  const [help, setHelp] = useState(false);
  const pocketbook = me.device === 'pocketbook';
  const email = me.kindle_email ?? '';
  const sender = me.sender_email ?? '—';

  // The server remembers the test book, so "did it arrive?" is still there after a trip to Amazon
  const test = useMutation({
    mutationFn: sendTestBook,
    onSuccess: () => {
      setHelp(false);
      setUser({ ...me, test_sent_at: new Date().toISOString() });
    },
  });
  const arrived = useMutation({
    mutationFn: confirmSetup,
    onSuccess: ({ user }) => {
      setUser(user);
      onDone();
    },
  });
  const sentAt = me.test_sent_at
    ? new Date(me.test_sent_at).toLocaleTimeString(lang === 'de' ? 'de-DE' : 'en-GB', { hour: '2-digit', minute: '2-digit' })
    : null;
  const reasons = pocketbook
    ? (['confirm', 'address', 'sync'] as const).map((key) => t(`setup.test.pocketbookHelp.${key}`, { email, sender }))
    : (['sender', 'address', 'rejected', 'slow'] as const).map((key) => t(`setup.test.kindleHelp.${key}`, { email, sender }));

  return (
    <div>
      <StepHead title={t('setup.test.title')}>
        {t(pocketbook ? 'setup.test.pocketbookText' : 'setup.test.kindleText', { email })}
      </StepHead>
      <div className="g1-stack">
        {sentAt && (
          <Callout tone="info" title={t('setup.test.sentAt', { time: sentAt })}>
            <div className="mt-3 flex flex-wrap gap-2">
              <button type="button" className="g1-btn g1-btn--primary g1-btn--sm" disabled={arrived.isPending} onClick={() => arrived.mutate()}>
                <IconCheck className="g1-icon" aria-hidden />
                {t('setup.test.arrived')}
              </button>
              <button type="button" className="g1-btn g1-btn--sm" aria-expanded={help} onClick={() => setHelp(true)}>
                {t('setup.test.notYet')}
              </button>
            </div>
          </Callout>
        )}
        {help && (
          <div className="g1-card">
            <h3 className="g1-card__title m-0">{t('setup.test.helpTitle')}</h3>
            <ol className="m-0 list-decimal pl-5 text-muted">
              {reasons.map((reason) => (
                <li key={reason} className="mb-2 break-words">
                  {reason}
                </li>
              ))}
            </ol>
            <div className="g1-card__foot">
              <button type="button" className="g1-btn g1-btn--sm" onClick={onFix}>
                {t('setup.test.fixAddress')}
              </button>
            </div>
          </div>
        )}
        <ErrorCallout code={errorCode(test.error ?? arrived.error)} />
        <div className="flex flex-wrap gap-2">
          <BackButton onClick={onBack} />
          <button
            type="button"
            className={sentAt ? 'g1-btn' : 'g1-btn g1-btn--primary'}
            disabled={test.isPending}
            onClick={() => test.mutate()}
          >
            {sentAt ? t('setup.test.sendAgain') : t('setup.test.send')}
          </button>
        </div>
      </div>
    </div>
  );
}

function DoneStep({ me, onChange }: { me: Me; onChange: (step: Step) => void }) {
  const { t } = useI18n();
  const other = !me.kindle_email;
  const title = other ? 'setup.done.otherTitle' : me.device === 'pocketbook' ? 'setup.done.pocketbookTitle' : 'setup.done.kindleTitle';
  return (
    <div className="g1-stack">
      <Callout tone="success" title={t(title)}>
        {other ? t('setup.done.otherText') : t('setup.done.text')}
      </Callout>
      <div className="flex flex-wrap gap-2">
        <Link to="/" className="g1-btn g1-btn--primary">
          {t('setup.done.action')} <IconArrowRight className="g1-icon g1-arrow" aria-hidden />
        </Link>
        {!other && (
          <button type="button" className="g1-btn g1-btn--ghost" onClick={() => onChange('address')}>
            {t('setup.done.change')}
          </button>
        )}
        <button type="button" className="g1-btn g1-btn--ghost" onClick={() => onChange('choose')}>
          {t('setup.done.changeDevice')}
        </button>
      </div>
    </div>
  );
}
