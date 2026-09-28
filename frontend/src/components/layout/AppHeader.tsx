import { useState } from 'react';
import {
  Activity, AlertTriangle, BarChart3, Bot, CloudSun, Compass, Droplets, FlaskConical,
  History, Leaf, Map, MapPinned, Menu, Mic, Moon, PanelLeftClose, PanelLeftOpen, Plane, Settings, Sun, Waves, X,
} from 'lucide-react';
import { LANGUAGE_LABELS, t, useLanguage, type Language } from '../../i18n';

export type AppPage = 'dashboard' | 'chat' | 'current' | 'forecast' | 'map' | 'alerts' | 'advisory' | 'agriculture' | 'aviation' | 'marine' | 'historical' | 'climate' | 'prediction' | 'nwp' | 'settings';

interface AppHeaderProps {
  page: AppPage;
  onNavigate: (page: AppPage) => void;
  darkMode: boolean;
  onToggleTheme: () => void;
  sidebarCollapsed: boolean;
  onToggleSidebar: () => void;
}

const navigation: { id: AppPage; label: string; icon: typeof CloudSun }[] = [
  { id: 'dashboard', label: 'Dashboard', icon: Activity },
  { id: 'chat', label: 'Chat', icon: Bot },
  { id: 'current', label: 'Current Weather', icon: CloudSun },
  { id: 'forecast', label: 'Forecast', icon: Sun },
  { id: 'map', label: 'Weather Map', icon: Map },
  { id: 'alerts', label: 'Alerts', icon: AlertTriangle },
  { id: 'advisory', label: 'Advisory', icon: Compass },
  { id: 'agriculture', label: 'Agriculture', icon: Leaf },
  { id: 'aviation', label: 'Aviation', icon: Plane },
  { id: 'marine', label: 'Marine', icon: Waves },
  { id: 'historical', label: 'Historical Weather', icon: History },
  { id: 'climate', label: 'Climate Analysis', icon: BarChart3 },
  { id: 'prediction', label: 'Rainfall Prediction', icon: Droplets },
  { id: 'nwp', label: 'NWP Models', icon: FlaskConical },
  { id: 'settings', label: 'Settings', icon: Settings },
];

export default function AppHeader({ page, onNavigate, darkMode, onToggleTheme, sidebarCollapsed, onToggleSidebar }: AppHeaderProps) {
  const { language, setLanguage } = useLanguage();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const selectPage = (next: AppPage) => { onNavigate(next); setMobileMenuOpen(false); };
  const buttonClass = (item: AppPage, compact = false, iconOnly = false) => `group flex w-full items-center gap-3 rounded-xl text-left text-sm font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${compact ? 'flex-col justify-center gap-1 px-1 py-2' : iconOnly ? 'justify-center px-2 py-2.5' : 'px-3 py-2.5'} ${page === item || (item === 'dashboard' && page === 'current') ? 'bg-blue-50 text-brand dark:bg-blue-950/60 dark:text-blue-300' : 'text-muted hover:bg-slate-50 hover:text-ink dark:hover:bg-slate-800 dark:hover:text-white'}`;
  return <>
    <header className="app-topbar sticky top-0 z-30 flex h-[72px] items-center justify-between border-b border-line bg-white/95 px-4 backdrop-blur sm:px-6">
      <a href="#main" className="flex min-w-0 items-center gap-3 rounded-lg focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand text-white shadow-sm"><CloudSun aria-hidden="true" size={23} strokeWidth={1.8} /></span>
        <span><span className="block text-lg font-bold tracking-tight text-ink">WeatherGPT</span><span className="hidden text-xs text-muted sm:block">Weather intelligence platform</span></span>
      </a>
      <div className="flex items-center gap-2">
        <button type="button" aria-label="Find a location" title="Find a location" onClick={() => selectPage('current')} className="flex h-10 items-center gap-2 rounded-lg border border-line bg-white px-3 text-sm font-medium text-muted transition hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand"><MapPinned size={17}/><span className="hidden sm:inline">Location</span></button>
        <button type="button" aria-label="Open voice assistant" title="Open voice assistant" onClick={() => selectPage('chat')} className="flex h-10 w-10 items-center justify-center rounded-lg border border-line bg-white text-muted transition hover:text-brand focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand"><Mic size={17}/></button>
        <span className="hidden rounded-lg border border-line px-3 py-2 text-xs text-muted xl:block">Live, forecast, historical & model data</span>
        <label className="sr-only" htmlFor="language-select">Language</label>
        <select id="language-select" aria-label="Language" value={language} onChange={(event) => setLanguage(event.target.value as Language)} className="min-h-10 rounded-lg border border-line bg-white px-2 text-sm text-ink"><option value="en">{LANGUAGE_LABELS.en}</option><option value="mr">{LANGUAGE_LABELS.mr}</option><option value="hi">{LANGUAGE_LABELS.hi}</option></select>
        <button type="button" aria-label={darkMode ? 'Switch to light theme' : 'Switch to dark theme'} title={darkMode ? 'Switch to light theme' : 'Switch to dark theme'} onClick={onToggleTheme} className="flex h-10 w-10 items-center justify-center rounded-lg border border-line bg-white text-muted transition hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand">{darkMode ? <Sun size={18}/> : <Moon size={18}/>}</button>
        <button type="button" aria-label={mobileMenuOpen ? 'Close navigation menu' : 'Open navigation menu'} aria-expanded={mobileMenuOpen} onClick={() => setMobileMenuOpen((open) => !open)} className="flex h-10 w-10 items-center justify-center rounded-lg border border-line bg-white text-muted lg:hidden">{mobileMenuOpen ? <X size={18}/> : <Menu size={18}/>}</button>
      </div>
    </header>
    <aside className={`app-sidebar fixed bottom-0 left-0 top-[72px] z-20 hidden flex-col border-r border-line bg-white transition-[width] duration-200 lg:flex ${sidebarCollapsed ? 'w-[76px]' : 'w-[252px]'}`} aria-label="Application sections">
      <div className={`flex items-center pb-2 pt-5 ${sidebarCollapsed ? 'justify-center px-2' : 'justify-between px-4'}`}>{!sidebarCollapsed && <p className="px-3 text-[10px] font-bold uppercase tracking-[.16em] text-slate-400">Weather workspace</p>}<button type="button" onClick={onToggleSidebar} aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'} title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'} className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-muted hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand dark:hover:bg-slate-800">{sidebarCollapsed ? <PanelLeftOpen size={17}/> : <PanelLeftClose size={17}/>}</button></div>
      <nav aria-label="Main navigation" className="min-h-0 flex-1 space-y-1 overflow-y-auto px-3 pb-5">
        {navigation.map(({ id, label, icon: Icon }) => <button key={id} type="button" aria-current={page === id || (id === 'dashboard' && page === 'current') ? 'page' : undefined} onClick={() => selectPage(id)} title={sidebarCollapsed ? t(language, label) : undefined} className={buttonClass(id, false, sidebarCollapsed)}><Icon size={17} aria-hidden="true"/>{!sidebarCollapsed && <><span>{t(language, label)}</span>{id === 'nwp' && <span className="ml-auto rounded-full bg-slate-100 px-1.5 py-0.5 text-[9px] text-muted dark:bg-slate-700">Soon</span>}</>}</button>)}
      </nav>
      {!sidebarCollapsed && <div className="border-t border-line p-4"><p className="text-xs font-semibold text-ink">Data integrity</p><p className="mt-1 text-[11px] leading-5 text-muted">Sources are labelled by type. Unsupported integrations are shown as unavailable.</p></div>}
    </aside>
    {mobileMenuOpen && <div className="fixed inset-0 top-[72px] z-40 bg-black/30 lg:hidden" onClick={() => setMobileMenuOpen(false)}>
      <nav aria-label="Mobile navigation menu" className="max-h-[calc(100vh-72px)] overflow-y-auto border-b border-line bg-white p-3 shadow-xl dark:bg-slate-900" onClick={(event) => event.stopPropagation()}>
        {navigation.map(({ id, label, icon: Icon }) => <button key={id} type="button" aria-current={page === id ? 'page' : undefined} onClick={() => selectPage(id)} className={buttonClass(id)}><Icon size={17} aria-hidden="true"/><span>{t(language, label)}</span></button>)}
      </nav>
    </div>}
    <nav aria-label="Mobile quick navigation" className="mobile-bottom-nav fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t border-line bg-white/95 px-2 pb-[env(safe-area-inset-bottom)] pt-1 backdrop-blur lg:hidden">
      {(['dashboard', 'forecast', 'map', 'alerts', 'chat'] as AppPage[]).map((id) => { const item = navigation.find((entry) => entry.id === id)!; const label = id === 'dashboard' ? 'Home' : id === 'chat' ? 'AI' : item.label; const Icon = item.icon; return <button key={id} type="button" aria-label={`Mobile navigation: ${t(language, label)}`} aria-current={page === id || (id === 'dashboard' && page === 'current') ? 'page' : undefined} onClick={() => selectPage(id)} className={buttonClass(id, true)}><Icon size={19} aria-hidden="true"/><span className="max-w-full truncate text-[10px]">{t(language, label)}</span></button>; })}
    </nav>
  </>;
}
