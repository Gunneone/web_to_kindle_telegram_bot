import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Route, Routes } from 'react-router';
import { Layout } from './components/Layout';
import { RequireUser } from './components/RequireUser';
import { I18nProvider } from './i18n';
import { ApiError } from './lib/api';
import { BookPage } from './routes/Book';
import { History } from './routes/History';
import { Home } from './routes/Home';
import { NotFound } from './routes/NotFound';
import { Privacy } from './routes/Privacy';
import { Settings } from './routes/Settings';
import { Setup } from './routes/Setup';
import { SignIn } from './routes/SignIn';
import { Verify } from './routes/Verify';
import './styles.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: (count, error) => !(error instanceof ApiError) && count < 2,
    },
  },
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <I18nProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<Home />} />
              <Route path="signin" element={<SignIn />} />
              <Route path="signin/verify" element={<Verify />} />
              <Route path="privacy" element={<Privacy />} />
              {/* A book can belong to a visitor who tried Eselsohr without signing in */}
              <Route path="books/:id" element={<BookPage />} />
              <Route element={<RequireUser />}>
                <Route path="history" element={<History />} />
                <Route path="setup" element={<Setup />} />
                <Route path="settings" element={<Settings />} />
              </Route>
              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </I18nProvider>
    </QueryClientProvider>
  </StrictMode>,
);
