import { useI18n } from '../i18n';
import type { Me } from '../lib/api';

/** Why a book mailed to the e-reader may not show up, most likely first (Kindle or PocketBook). */
export function ArrivalReasons({ me }: { me: Me }) {
  const { t } = useI18n();
  const email = me.kindle_email ?? '';
  const sender = me.sender_email ?? '—';
  const reasons =
    me.device === 'pocketbook'
      ? (['confirm', 'address', 'sync'] as const).map((key) => t(`setup.test.pocketbookHelp.${key}`, { email, sender }))
      : (['sender', 'address', 'rejected', 'slow'] as const).map((key) => t(`setup.test.kindleHelp.${key}`, { email, sender }));
  return (
    <ol className="m-0 list-decimal pl-5 text-muted">
      {reasons.map((reason) => (
        <li key={reason} className="mb-2 break-words">
          {reason}
        </li>
      ))}
    </ol>
  );
}
