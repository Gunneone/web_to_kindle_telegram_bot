import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getSession, type Me, type SessionInfo } from './api';

export const SESSION_KEY = ['session'] as const;

export function useSession() {
  return useQuery({ queryKey: SESSION_KEY, queryFn: getSession, staleTime: 60_000 });
}

/** The signed-in account, or null while loading or signed out. */
export function useMe(): Me | null {
  return useSession().data?.user ?? null;
}

/** After signing in, out or changing the account: fresh session, and nothing cached from the old one. */
export function useResetSession() {
  const client = useQueryClient();
  return async () => {
    client.removeQueries({ predicate: (query) => query.queryKey[0] !== 'session' });
    await client.invalidateQueries({ queryKey: SESSION_KEY });
  };
}

/** Put an updated account into the cached session, so every screen shows it at once. */
export function useSetUser() {
  const client = useQueryClient();
  return (user: Me) =>
    client.setQueryData<SessionInfo>(SESSION_KEY, (old) => (old ? { ...old, user } : old));
}
