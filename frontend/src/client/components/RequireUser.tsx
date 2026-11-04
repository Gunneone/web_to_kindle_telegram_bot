import { Navigate, Outlet, useLocation } from 'react-router';
import { useSession } from '../lib/session';

/** Routes inside need a signed-in account; everyone else goes to the sign-in page and comes back. */
export function RequireUser() {
  const session = useSession();
  const { pathname, search } = useLocation();
  if (session.isPending) return null;
  if (!session.data?.user) return <Navigate to={`/signin?next=${encodeURIComponent(pathname + search)}`} replace />;
  return <Outlet />;
}
