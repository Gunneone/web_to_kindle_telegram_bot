import { IconSend } from '@tabler/icons-react';
import { Link, useLocation } from 'react-router';
import { useI18n } from '../i18n';
import type { Book } from '../lib/api';
import { formatDate } from '../lib/format';
import { useMe } from '../lib/session';
import { Callout } from './Callout';

/**
 * "You already sent this to your Kindle": a send the server held back because the page went to the Kindle
 * before. Amazon never says whether a book arrived, so sending it anyway stays one click away.
 */
export function AlreadySent({
  previous,
  named,
  busy,
  onSend,
  onCancel,
  showOpen = true,
}: {
  /** The earlier book that went to the Kindle */
  previous: Book;
  /** Say which book (when there are several results or the list is near) */
  named: boolean;
  busy: boolean;
  onSend: () => void;
  onCancel: () => void;
  /** Link to the earlier book (not when it is the page already open) */
  showOpen?: boolean;
}) {
  const { t, lang } = useI18n();
  const me = useMe();
  const location = useLocation();
  const vars = { title: previous.title, email: me?.kindle_email ?? '', date: formatDate(previous.created_at, lang) };
  return (
    <Callout tone="warning" title={t(named ? 'send.duplicateNamed' : 'send.duplicateTitle', vars)}>
      {t('send.duplicateText')}
      <div className="mt-3 flex flex-wrap gap-2">
        <button type="button" className="g1-btn g1-btn--sm g1-btn--primary" disabled={busy} onClick={onSend}>
          <IconSend className="g1-icon" aria-hidden />
          {t('send.sendAgain')}
        </button>
        {showOpen && previous.can_download && (
          <Link className="g1-btn g1-btn--sm" to={`/books/${previous.id}`} state={{ from: location.pathname + location.search }}>
            {t('send.openIt')}
          </Link>
        )}
        <button type="button" className="g1-btn g1-btn--sm g1-btn--ghost" onClick={onCancel}>
          {t('common.cancel')}
        </button>
      </div>
    </Callout>
  );
}
