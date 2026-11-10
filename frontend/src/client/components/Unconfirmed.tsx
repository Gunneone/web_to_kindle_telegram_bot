import { Link } from 'react-router';
import { useI18n } from '../i18n';
import { useMe } from '../lib/session';
import { Callout } from './Callout';

/**
 * Sending works before the setup is finished, but nobody knows yet whether books arrive: Amazon drops
 * mail from senders that aren't approved without a word. Said wherever books can be sent, with the way out.
 */
export function UnconfirmedCallout() {
  const { t } = useI18n();
  const me = useMe();
  if (!me?.kindle_email || me.setup_verified) return null;
  return (
    <Callout tone="warning" title={t('send.unverifiedTitle')}>
      {t('send.unverified', { email: me.kindle_email })}{' '}
      <Link className="g1-link" to="/setup">
        {t('send.finishSetup')}
      </Link>
    </Callout>
  );
}

/** The same, as one line next to a "Send to Kindle" button. */
export function UnconfirmedNote() {
  const { t } = useI18n();
  const me = useMe();
  if (!me?.kindle_email || me.setup_verified) return null;
  return (
    <p className="m-0 text-sm text-muted">
      {t('book.unverified')}{' '}
      <Link className="g1-link" to="/setup">
        {t('send.finishSetup')}
      </Link>
    </p>
  );
}
