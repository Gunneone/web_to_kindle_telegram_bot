import { useMutation } from '@tanstack/react-query';
import { useState, type FormEvent } from 'react';
import { useI18n } from '../i18n';
import { ApiError, startEmailSignIn, verifyEmailCode } from '../lib/api';
import { ErrorCallout } from './Callout';

/** Email, then the 6-digit code from the mail. Calls `onDone` once the code is accepted. */
export function EmailSignIn({ onDone }: { onDone: () => void }) {
  const { t, lang } = useI18n();
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [sentTo, setSentTo] = useState<string | null>(null);

  const start = useMutation({
    mutationFn: (address: string) => startEmailSignIn(address, lang),
    onSuccess: (_data, address) => {
      setSentTo(address);
      setCode('');
    },
  });
  const verify = useMutation({
    mutationFn: ({ address, value }: { address: string; value: string }) => verifyEmailCode(address, value),
    onSuccess: onDone,
  });
  const error = (start.error ?? verify.error) as ApiError | null;

  const submitEmail = (event: FormEvent) => {
    event.preventDefault();
    verify.reset();
    start.mutate(email.trim());
  };
  const submitCode = (event: FormEvent) => {
    event.preventDefault();
    if (sentTo) verify.mutate({ address: sentTo, value: code.trim() });
  };

  if (sentTo) {
    return (
      <form onSubmit={submitCode} className="g1-stack">
        <p className="m-0 text-muted">{t('signin.codeSent', { email: sentTo })}</p>
        <div>
          <label className="g1-label" htmlFor="signin-code">
            {t('signin.codeLabel')}
          </label>
          <input
            id="signin-code"
            className="g1-input font-mono tracking-[0.3em]"
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern="[0-9]{6}"
            maxLength={6}
            placeholder={t('signin.codePlaceholder')}
            value={code}
            onChange={(event) => setCode(event.target.value.replace(/\D/g, ''))}
            autoFocus
            required
          />
        </div>
        <ErrorCallout code={error?.code} />
        <div className="flex flex-wrap gap-2">
          <button type="submit" className="g1-btn g1-btn--primary" disabled={code.length !== 6 || verify.isPending}>
            {t('signin.codeSubmit')}
          </button>
          <button
            type="button"
            className="g1-btn g1-btn--ghost"
            disabled={start.isPending}
            onClick={() => start.mutate(sentTo)}
          >
            {t('signin.resend')}
          </button>
          <button type="button" className="g1-btn g1-btn--ghost" onClick={() => setSentTo(null)}>
            {t('signin.otherEmail')}
          </button>
        </div>
      </form>
    );
  }

  return (
    <form onSubmit={submitEmail} className="g1-stack">
      <div>
        <label className="g1-label" htmlFor="signin-email">
          {t('signin.emailLabel')}
        </label>
        <input
          id="signin-email"
          className="g1-input"
          type="email"
          autoComplete="email"
          placeholder={t('signin.emailPlaceholder')}
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />
      </div>
      <ErrorCallout code={error?.code} />
      <div>
        <button type="submit" className="g1-btn g1-btn--primary" disabled={!email || start.isPending}>
          {t('signin.emailSubmit')}
        </button>
      </div>
    </form>
  );
}
