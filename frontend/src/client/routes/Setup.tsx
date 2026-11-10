import { useMutation } from '@tanstack/react-query';
import { IconArrowLeft, IconArrowRight, IconArrowUpRight, IconCheck, IconCopy, IconTrash } from '@tabler/icons-react';
import { useState, type FormEvent, type ReactNode } from 'react';
import { Link, useSearchParams } from 'react-router';
import { ArrivalReasons } from '../components/ArrivalHelp';
import { Callout, ErrorCallout } from '../components/Callout';
import { Saved, useSavedFlash } from '../components/Saved';
import { PageHead } from '../components/Text';
import { useI18n } from '../i18n';
import { confirmSetup, errorCode, sendTestBook, updateMe, type Me } from '../lib/api';
import { useMe, useSetUser } from '../lib/session';

type Step = 'address' | 'sender' | 'test' | 'done';
const NUMBERED = ['address', 'sender', 'test'] as const;

/** Where someone left off: the server remembers the address, the test book and whether it arrived. */
function firstStep(me: Me, asked: string | null): Step {
  if (asked === 'address' || !me.kindle_email) return 'address';
  if (asked === 'test') return 'test'; // from "not on your Kindle?": send a test book
  if (me.setup_verified) return 'done';
  return me.test_sent_at ? 'test' : 'sender';
}

/**
 * Setting up an e-reader, one step at a time: your address, approve our sender, a test book. Each step
 * survives a reload, so going off to Amazon and coming back picks up where it was. Kindle and PocketBook
 * take the same path (both get books by email); only the wording of the sender and test steps follows the
 * address, since approving a sender works differently on each. Any other reader needs no setup: every book
 * can be downloaded. A saved address is used until it is removed, which only the address step does.
 */
export function Setup() {
  const me = useMe();
  const [params] = useSearchParams();
  if (!me) return null;
  return <Wizard me={me} initial={firstStep(me, params.get('step'))} />;
}

function Wizard({ me, initial }: { me: Me; initial: Step }) {
  const { t } = useI18n();
  const [step, setStep] = useState<Step>(initial);
  // The address step saves on its button: the next step confirms it, like settings that save on change
  const [savedAddress, setSavedAddress] = useState<string | null>(null);

  const index = (NUMBERED as readonly Step[]).indexOf(step);
  return (
    <div className="g1-container esel-column">
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

      {step === 'address' && (
        <AddressStep
          me={me}
          onDone={(saved) => {
            setSavedAddress(saved);
            setStep('sender');
          }}
        />
      )}
      {step === 'sender' && (
        <SenderStep me={me} savedAddress={savedAddress} onBack={() => setStep('address')} onDone={() => setStep('test')} />
      )}
      {step === 'test' && <TestStep me={me} onBack={() => setStep('sender')} onFix={() => setStep('address')} onDone={() => setStep('done')} />}
      {step === 'done' && <DoneStep onChange={() => setStep('address')} />}
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

function AddressStep({
  me,
  onDone,
}: {
  me: Me;
  /** With the address just saved, or null when it didn't change */
  onDone: (saved: string | null) => void;
}) {
  const { t } = useI18n();
  const setUser = useSetUser();
  const [address, setAddress] = useState(me.kindle_email ?? '');
  const [storeSaved, flashStore] = useSavedFlash();
  const [confirmingRemove, setConfirmingRemove] = useState(false);
  const [removed, setRemoved] = useState<string | null>(null);
  // The Amazon store only matters for a Kindle; a PocketBook address ends in @pbsync.com
  const pocketbook = /@pbsync\.com\s*$/i.test(address);
  const save = useMutation({
    mutationFn: (value: string) => updateMe({ kindle_email: value }),
    onSuccess: ({ user }) => {
      setUser(user);
      onDone(user.kindle_email);
    },
  });
  const store = useMutation({
    mutationFn: (value: string) => updateMe({ amazon_store: value }),
    onSuccess: ({ user }) => {
      setUser(user);
      flashStore();
    },
  });
  // The one way an address goes away: asked for here, and confirmed
  const remove = useMutation({
    mutationFn: () => updateMe({ kindle_email: '' }),
    onSuccess: ({ user }) => {
      setRemoved(me.kindle_email);
      setUser(user);
      setAddress('');
      setConfirmingRemove(false);
    },
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const value = address.trim();
    if (value === me.kindle_email) onDone(null);
    else save.mutate(value);
  };

  return (
    <form onSubmit={submit}>
      {removed && (
        <div className="mb-5">
          <Callout tone="success" title={t('setup.address.removed', { email: removed })}>
            {t('setup.address.removedText')}
          </Callout>
        </div>
      )}
      <StepHead title={t('setup.address.title')}>{t('setup.address.text')}</StepHead>
      <div className="g1-stack">
        <ul className="m-0 list-disc pl-5 text-muted">
          <li className="mb-2">
            {t('setup.address.kindleHint')}{' '}
            <a className="g1-link inline-flex items-center gap-1" href={me.amazon_devices_url} target="_blank" rel="noopener noreferrer">
              {t('setup.address.findLink')} <IconArrowUpRight className="g1-icon" aria-hidden />
            </a>
          </li>
          <li className="mb-2">{t('setup.address.pocketbookHint')}</li>
          <li>{t('setup.address.otherHint')}</li>
        </ul>
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
            placeholder={t('setup.address.placeholder')}
            value={address}
            onChange={(event) => setAddress(event.target.value)}
            required
          />
        </div>
        {!pocketbook && (
          <div>
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <label className="g1-label" htmlFor="setup-store">
                {t('setup.address.storeLabel')}
              </label>
              <Saved show={storeSaved} />
            </div>
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
        <ErrorCallout code={errorCode(save.error ?? store.error ?? remove.error)} />
        <div className="flex flex-wrap gap-2">
          <button type="submit" className="g1-btn g1-btn--primary" disabled={!address.trim() || save.isPending}>
            {t('setup.address.next')} <IconArrowRight className="g1-icon g1-arrow" aria-hidden />
          </button>
        </div>
        {me.kindle_email && (
          <div className="border-t border-line pt-5">
            {confirmingRemove ? (
              <Callout tone="danger" title={t('setup.address.removeTitle', { email: me.kindle_email })}>
                {t('setup.address.removeText')}
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="g1-btn g1-btn--sm text-danger [--g1-edge:var(--g1-danger)]"
                    disabled={remove.isPending}
                    autoFocus
                    onClick={() => remove.mutate()}
                  >
                    {t('setup.address.removeConfirm')}
                  </button>
                  <button type="button" className="g1-btn g1-btn--sm g1-btn--ghost" onClick={() => setConfirmingRemove(false)}>
                    {t('common.cancel')}
                  </button>
                </div>
              </Callout>
            ) : (
              <button type="button" className="g1-btn g1-btn--ghost g1-btn--sm" onClick={() => setConfirmingRemove(true)}>
                <IconTrash className="g1-icon" aria-hidden />
                {t('setup.address.remove')}
              </button>
            )}
          </div>
        )}
      </div>
    </form>
  );
}

function SenderStep({
  me,
  savedAddress,
  onBack,
  onDone,
}: {
  me: Me;
  savedAddress: string | null;
  onBack: () => void;
  onDone: () => void;
}) {
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
      {savedAddress && (
        <p className="m-0 mb-4">
          <Saved show>{t('setup.address.saved', { email: savedAddress })}</Saved>
        </p>
      )}
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
            <ArrivalReasons me={me} />
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

function DoneStep({ onChange }: { onChange: () => void }) {
  const { t } = useI18n();
  return (
    <div className="g1-stack">
      <Callout tone="success" title={t('setup.done.title')}>
        {t('setup.done.text')}
      </Callout>
      <div className="flex flex-wrap gap-2">
        <Link to="/" className="g1-btn g1-btn--primary">
          {t('setup.done.action')} <IconArrowRight className="g1-icon g1-arrow" aria-hidden />
        </Link>
        <button type="button" className="g1-btn g1-btn--ghost" onClick={onChange}>
          {t('setup.done.change')}
        </button>
      </div>
    </div>
  );
}
