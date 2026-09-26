import { useState } from 'react';
import AppHeader, { type AppPage } from './components/layout/AppHeader';
import ChatPanel from './components/chat/ChatPanel';
import Dashboard from './pages/Dashboard';
import Forecast from './pages/Forecast';
import Alerts from './pages/Alerts';
import Advisory from './pages/Advisory';
import Historical from './pages/Historical';
import { LanguageContext, readLanguage, type Language } from './i18n';

export default function App() {
  const [page, setPage] = useState<AppPage>('dashboard');
  const [language, setLanguageState] = useState<Language>(readLanguage);
  function setLanguage(next: Language) { setLanguageState(next); try { window.localStorage.setItem('weathergpt-language', next); } catch { /* private browsing may disable storage */ } }
  return (
    <LanguageContext.Provider value={{ language, setLanguage }}><div lang={language} className="min-h-screen bg-canvas text-ink">
      <AppHeader page={page} onNavigate={setPage} />
      {page === 'dashboard' ? <Dashboard onOpenChat={() => setPage('chat')} onOpenAlerts={() => setPage('alerts')} /> : page === 'chat' ? <ChatPanel /> : page === 'alerts' ? <Alerts /> : page === 'advisory' ? <Advisory /> : page === 'historical' ? <Historical /> : <Forecast />}
    </div></LanguageContext.Provider>
  );
}
