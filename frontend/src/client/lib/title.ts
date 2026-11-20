import { useEffect } from 'react';
import { useI18n } from '../i18n';

/**
 * The browser tab's title: `{page} · Eselsohr`, or the start page's own title without a page. While the page
 * name isn't known yet (a book still loading), pass `undefined` and the title stays as it was.
 */
export function usePageTitle(page: string | null | undefined, home = false) {
  const { t } = useI18n();
  useEffect(() => {
    if (home) document.title = t('titles.home');
    else if (page) document.title = t('titles.page', { page });
  }, [page, home, t]);
}
