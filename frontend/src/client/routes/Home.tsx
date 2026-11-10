import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { sharedLink } from '../lib/links';
import { useMe, useSession } from '../lib/session';
import { Landing } from './Landing';
import { Send } from './Send';

/**
 * The start page: the form when signed in, the pitch (with a try form) when not. A link handed over
 * by the bookmarklet or the share sheet (`?url=`, `?text=`) fills the form; it is then taken out of
 * the address, so reloading doesn't bring it back.
 */
export function Home() {
  const session = useSession();
  const me = useMe();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [shared] = useState(() => sharedLink(params));

  useEffect(() => {
    if (params.has('url') || params.has('text') || params.has('title')) void navigate('/', { replace: true });
  }, [params, navigate]);

  if (session.isPending) return null;
  return me ? <Send initialLink={shared} /> : <Landing initialLink={shared} />;
}
