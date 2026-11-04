import {
  IconBrandGithub,
  IconBrandLinkedin,
  IconBrandTelegram,
  IconLanguage,
  IconMoon,
  IconSun,
} from '@tabler/icons-react';
import { Link, NavLink, Outlet } from 'react-router';
import { useI18n } from '../i18n';
import { useMe } from '../lib/session';
import { Brand } from './Brand';

const SOCIAL = [
  { label: 'GitHub', href: 'https://github.com/gunneone', icon: IconBrandGithub },
  { label: 'LinkedIn', href: 'https://linkedin.com/in/gunneone', icon: IconBrandLinkedin },
  { label: 'Telegram', href: 'https://t.me/gunneone', icon: IconBrandTelegram },
];

export function Layout() {
  const { t, lang, setLang } = useI18n();
  const me = useMe();
  return (
    <>
      <a className="g1-skip-link" href="#main">
        {t('common.skipToContent')}
      </a>
      <header className="g1-header">
        <div className="g1-container g1-container--wide g1-header__inner">
          <Brand />
          {me && (
            <nav className="g1-nav" aria-label={t('nav.main')}>
              <NavLink to="/" end>
                {t('nav.send')}
              </NavLink>
              <NavLink to="/history">{t('nav.history')}</NavLink>
              <NavLink to="/settings">{t('nav.settings')}</NavLink>
            </nav>
          )}
          <div className="g1-header__actions">
            {!me && (
              <Link to="/signin" className="g1-btn g1-btn--sm">
                {t('nav.signIn')}
              </Link>
            )}
            <button
              type="button"
              className="g1-btn g1-btn--ghost g1-btn--icon"
              onClick={() => setLang(lang === 'en' ? 'de' : 'en')}
              aria-label={t('common.switchLanguage')}
              title={t('common.switchLanguage')}
            >
              <IconLanguage className="g1-icon" aria-hidden />
            </button>
            <button
              type="button"
              className="g1-btn g1-btn--ghost g1-btn--icon"
              data-g1-theme-toggle
              aria-label={t('common.toggleTheme')}
            >
              <IconMoon className="g1-icon g1-when-light" aria-hidden />
              <IconSun className="g1-icon g1-when-dark" aria-hidden />
            </button>
          </div>
        </div>
      </header>
      <main id="main" className="flex-1">
        <Outlet />
      </main>
      <footer className="g1-footer">
        <div className="g1-container g1-container--wide">
          <div className="g1-footer__inner">
            <nav className="g1-footer__links" aria-label={t('nav.footer')}>
              <Link to="/privacy">{t('nav.privacy')}</Link>
              <a href="https://t.me/SubstackKindleBot" target="_blank" rel="noopener noreferrer">
                {t('nav.bot')}
              </a>
              <a href="https://github.com/Gunneone/web_to_kindle_telegram_bot" target="_blank" rel="noopener noreferrer">
                {t('nav.source')}
              </a>
              <a href="https://gunne.one">{t('nav.moreProjects')}</a>
            </nav>
            <div className="g1-footer__social">
              {SOCIAL.map(({ label, href, icon: Icon }) => (
                <a key={label} href={href} target="_blank" rel="noopener noreferrer" aria-label={label}>
                  <Icon className="g1-icon" aria-hidden />
                </a>
              ))}
            </div>
          </div>
          <div className="g1-footer__meta">
            <a className="g1-family" href="https://gunne.one">
              <img src={`${__G1_DS_URL__}/brand/g1-mark-48.png`} alt="" width={16} height={16} />
              {t('footer.family')}
            </a>
            <span>{t('footer.promise')}</span>
          </div>
        </div>
      </footer>
    </>
  );
}
