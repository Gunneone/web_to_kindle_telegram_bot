import { useMe, useSession } from '../lib/session';
import { Landing } from './Landing';
import { Send } from './Send';

/** The start page: the form when signed in, the pitch when not. */
export function Home() {
  const session = useSession();
  const me = useMe();
  if (session.isPending) return null;
  return me ? <Send /> : <Landing />;
}
