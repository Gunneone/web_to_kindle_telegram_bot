import { IconAlertTriangle, IconCheck, IconInfoCircle, IconX } from '@tabler/icons-react';
import type { ReactNode } from 'react';
import { useI18n } from '../i18n';

type Tone = 'info' | 'success' | 'warning' | 'danger';
const ICONS = { info: IconInfoCircle, success: IconCheck, warning: IconAlertTriangle, danger: IconX };

export function Callout({ tone, title, children }: { tone: Tone; title?: ReactNode; children?: ReactNode }) {
  const Icon = ICONS[tone];
  return (
    <div className={`g1-callout g1-callout--${tone}`} role={tone === 'danger' ? 'alert' : 'status'}>
      <Icon className="g1-icon" aria-hidden />
      <div>
        {title && <strong className="block">{title}</strong>}
        {children}
      </div>
    </div>
  );
}

/** An error from the API or the sign-in redirect, in words. */
export function ErrorCallout({ code }: { code: string | null | undefined }) {
  const { error } = useI18n();
  if (!code) return null;
  return <Callout tone="danger">{error(code)}</Callout>;
}
