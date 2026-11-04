import { useMutation } from '@tanstack/react-query';
import { IconMessageReport } from '@tabler/icons-react';
import { useId, useState, type FormEvent } from 'react';
import { useI18n } from '../i18n';
import { errorCode, FEEDBACK_MAX, FEEDBACK_REASONS, sendFeedback, type FeedbackReason } from '../lib/api';
import { Callout, ErrorCallout } from './Callout';

/** "Something wrong with this book?": a short report that goes to the admin in Telegram, with the EPUB. */
export function Feedback({ bookId }: { bookId: number }) {
  const { t } = useI18n();
  const id = useId();
  const [open, setOpen] = useState(false);
  const [reasons, setReasons] = useState<FeedbackReason[]>([]);
  const [message, setMessage] = useState('');
  const submit = useMutation({ mutationFn: () => sendFeedback(bookId, reasons, message.trim()) });

  if (submit.isSuccess) {
    return (
      <Callout tone="success" title={t('feedback.sentTitle')}>
        {t('feedback.sentText')}
      </Callout>
    );
  }

  if (!open) {
    return (
      <button type="button" className="g1-btn g1-btn--ghost g1-btn--sm" aria-expanded={false} onClick={() => setOpen(true)}>
        <IconMessageReport className="g1-icon" aria-hidden />
        {t('feedback.open')}
      </button>
    );
  }

  const toggle = (reason: FeedbackReason, on: boolean) =>
    setReasons((current) => (on ? [...current, reason] : current.filter((r) => r !== reason)));
  const ready = reasons.length > 0 || message.trim().length > 0;
  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (ready) submit.mutate();
  };

  return (
    <form className="g1-card g1-stack" onSubmit={onSubmit} aria-labelledby={`${id}-title`}>
      <div>
        <h3 id={`${id}-title`} className="m-0 text-base">
          {t('feedback.title')}
        </h3>
        <p className="m-0 mt-1 text-sm text-muted">{t('feedback.lead')}</p>
      </div>
      <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
        <legend className="g1-visually-hidden">{t('feedback.title')}</legend>
        {FEEDBACK_REASONS.map((reason) => (
          <label key={reason} className="flex items-start gap-3 text-sm">
            <input
              type="checkbox"
              className="mt-0.5 size-4"
              checked={reasons.includes(reason)}
              onChange={(event) => toggle(reason, event.target.checked)}
            />
            <span>{t(`feedback.reasons.${reason}`)}</span>
          </label>
        ))}
      </fieldset>
      <div>
        <label className="g1-label" htmlFor={`${id}-message`}>
          {t('feedback.messageLabel')}
        </label>
        <textarea
          id={`${id}-message`}
          className="g1-textarea"
          rows={3}
          maxLength={FEEDBACK_MAX}
          placeholder={t('feedback.messagePlaceholder')}
          value={message}
          onChange={(event) => setMessage(event.target.value)}
        />
      </div>
      <ErrorCallout code={errorCode(submit.error)} />
      <div className="flex flex-wrap gap-2">
        <button type="submit" className="g1-btn g1-btn--primary g1-btn--sm" disabled={!ready || submit.isPending}>
          {t('feedback.send')}
        </button>
        <button type="button" className="g1-btn g1-btn--ghost g1-btn--sm" onClick={() => setOpen(false)}>
          {t('common.cancel')}
        </button>
      </div>
    </form>
  );
}
