import { IconBrandGoogle, IconBrandTelegram } from '@tabler/icons-react';
import { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { EmailSignIn } from '../components/EmailSignIn';
import { ErrorCallout } from '../components/Callout';
import { PageHead } from '../components/Text';
import { useT } from '../i18n';
import { signInUrl } from '../lib/api';
import { safeNext } from '../lib/format';
import { useMe, useResetSession, useSession } from '../lib/session';

export function SignIn() {
  const t = useT();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const session = useSession();
  const me = useMe();
  const reset = useResetSession();
  const next = safeNext(params.get('next'));

  useEffect(() => {
    if (me) navigate(next, { replace: true });
  }, [me, next, navigate]);

  const providers = session.data?.providers;
  // Only name the ways in that are switched on
  const lead = providers?.telegram ? (providers.google ? 'all' : 'telegram') : providers?.google ? 'google' : 'email';
  return (
    <div className="g1-container g1-container--prose">
      <PageHead
        eyebrow={t('signin.eyebrow')}
        title={t('signin.title')}
        lead={
          session.isPending ? undefined : (
            <>
              {t(`signin.lead.${lead}`)}
              {/* No "sign up" anywhere: the first sign-in makes the account */}
              <span className="mt-2 block">{t('signin.newHere')}</span>
            </>
          )
        }
      />
      <div className="g1-stack">
        <ErrorCallout code={params.get('error')} />
        {(providers?.telegram || providers?.google) && (
          // Stacked and as wide as the email field below, so the three ways in read as equals
          <div className="flex flex-col gap-3">
            {providers.telegram && (
              <a className="g1-btn g1-btn--lg w-full justify-center" href={signInUrl('telegram', next)}>
                <IconBrandTelegram className="g1-icon" aria-hidden />
                {t('signin.telegram')}
              </a>
            )}
            {providers.google && (
              <a className="g1-btn g1-btn--lg w-full justify-center" href={signInUrl('google', next)}>
                <IconBrandGoogle className="g1-icon" aria-hidden />
                {t('signin.google')}
              </a>
            )}
          </div>
        )}
        {(providers?.telegram || providers?.google) && <p className="g1-eyebrow m-0">{t('common.or')}</p>}
        <EmailSignIn next={next} onDone={() => void reset()} />
      </div>
    </div>
  );
}
