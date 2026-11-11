import { useMutation } from '@tanstack/react-query';
import { useEffect, useRef } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router';
import { ErrorCallout } from '../components/Callout';
import { PageHead } from '../components/Text';
import { useT } from '../i18n';
import { ApiError, verifyEmailToken } from '../lib/api';
import { safeNext } from '../lib/format';
import { useResetSession } from '../lib/session';
import { usePageTitle } from '../lib/title';

/** The page the sign-in mail links to. Signing in is a POST from here, so mail scanners can't use up the link. */
export function Verify() {
  const t = useT();
  usePageTitle(t('signin.title'));
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const reset = useResetSession();
  const token = params.get('token');
  const next = safeNext(params.get('next'));
  const started = useRef(false);

  const verify = useMutation({
    mutationFn: verifyEmailToken,
    onSuccess: async () => {
      await reset();
      navigate(next, { replace: true });
    },
  });

  useEffect(() => {
    if (token && !started.current) {
      started.current = true;
      verify.mutate(token);
    }
  }, [token, verify]);

  const error = (token ? verify.error : new ApiError('EXPIRED', 400)) as ApiError | null;
  return (
    <div className="g1-container g1-container--prose">
      <PageHead
        eyebrow={t('signin.eyebrow')}
        title={error ? t('signin.verifyFailed') : t('signin.verifying')}
      />
      <div className="g1-stack">
        <ErrorCallout code={error?.code} />
        {error && (
          <div>
            <Link className="g1-btn g1-btn--primary" to={next === '/' ? '/signin' : `/signin?next=${encodeURIComponent(next)}`}>
              {t('signin.verifyRetry')}
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
