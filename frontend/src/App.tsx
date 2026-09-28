import { useEffect, useState } from 'react';
import AppHeader, { type AppPage } from './components/layout/AppHeader';
import ChatPanel from './components/chat/ChatPanel';
import Dashboard from './pages/Dashboard';
import Forecast from './pages/Forecast';
import Alerts from './pages/Alerts';
import Advisory from './pages/Advisory';
import Historical from './pages/Historical';
import { AviationPage, ClimatePage, MarinePage, NwpPage, PredictionPage, SettingsPage, WeatherMapPage } from './pages/PlatformPages';
import { LanguageContext, readLanguage, type Language } from './i18n';

export default function App() {
  const [page, setPage] = useState<AppPage>('dashboard');
  const [language, setLanguageState] = useState<Language>(readLanguage);
  const [darkMode, setDarkMode] = useState(() => { try { return window.localStorage.getItem('weathergpt-theme') === 'dark'; } catch { return false; } });
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => { try { return window.localStorage.getItem('weathergpt-sidebar-collapsed') === 'true'; } catch { return false; } });
  function setLanguage(next: Language) { setLanguageState(next); try { window.localStorage.setItem('weathergpt-language', next); } catch { /* private browsing may disable storage */ } }
  function toggleTheme() { setDarkMode((current) => { const next = !current; try { window.localStorage.setItem('weathergpt-theme', next ? 'dark' : 'light'); } catch { /* private browsing may disable storage */ } return next; }); }
  function toggleSidebar() { setSidebarCollapsed((current) => { const next = !current; try { window.localStorage.setItem('weathergpt-sidebar-collapsed', String(next)); } catch { /* private browsing may disable storage */ } return next; }); }
  useEffect(() => { document.documentElement.classList.toggle('dark', darkMode); return () => document.documentElement.classList.remove('dark'); }, [darkMode]);
  const content = page === 'dashboard' || page === 'current'
    ? <Dashboard onOpenChat={() => setPage('chat')} onOpenAlerts={() => setPage('alerts')} onNavigate={setPage}/>
    : page === 'chat' ? <ChatPanel />
      : page === 'alerts' ? <Alerts onOpenAdvisory={() => setPage('advisory')} />
        : page === 'advisory' ? <Advisory />
          : page === 'agriculture' ? <Advisory initialActivity="AGRICULTURE" agricultureMode />
            : page === 'historical' ? <Historical />
              : page === 'forecast' ? <Forecast />
                : page === 'map' ? <WeatherMapPage />
                  : page === 'climate' ? <ClimatePage />
                    : page === 'aviation' ? <AviationPage />
                      : page === 'marine' ? <MarinePage />
                        : page === 'prediction' ? <PredictionPage />
                          : page === 'nwp' ? <NwpPage />
                            : <SettingsPage darkMode={darkMode} onToggleTheme={toggleTheme}/>;
  return (
    <LanguageContext.Provider value={{ language, setLanguage }}><div lang={language} className={`min-h-screen bg-canvas text-ink ${darkMode ? 'dark' : ''}`}>
      <AppHeader page={page} onNavigate={setPage} darkMode={darkMode} onToggleTheme={toggleTheme} sidebarCollapsed={sidebarCollapsed} onToggleSidebar={toggleSidebar} />
      <div className={`app-content min-h-[calc(100vh-72px)] transition-[margin] duration-200 ${sidebarCollapsed ? 'lg:ml-[76px]' : 'lg:ml-[252px]'}`}>{content}<footer className="app-footer px-5 pb-24 pt-2 text-center text-[11px] text-muted lg:pb-5">WeatherGPT · Data sources remain labelled by product and provenance.</footer></div>
    </div></LanguageContext.Provider>
  );
}
