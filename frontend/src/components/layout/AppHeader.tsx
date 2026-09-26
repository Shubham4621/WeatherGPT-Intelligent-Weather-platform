import { CloudSun } from 'lucide-react';
import { LANGUAGE_LABELS, t, useLanguage, type Language } from '../../i18n';

export type AppPage = 'dashboard' | 'chat' | 'forecast' | 'alerts' | 'advisory' | 'historical';

interface AppHeaderProps {
  page: AppPage;
  onNavigate: (page: AppPage) => void;
}

export default function AppHeader({ page, onNavigate }: AppHeaderProps) {
  const { language, setLanguage } = useLanguage();
  return (
    <header className="border-b border-line bg-white/85">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4 sm:px-8">
        <a href="#main" className="flex items-center gap-3 rounded-lg focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand text-white shadow-sm">
            <CloudSun aria-hidden="true" size={23} strokeWidth={1.8} />
          </span>
          <span>
            <span className="block text-lg font-bold tracking-tight text-ink">WeatherGPT</span>
            <span className="hidden text-xs text-muted sm:block">AI-Powered Weather Intelligence</span>
          </span>
        </a>
        <div className="flex items-center gap-2"><nav aria-label="Main navigation" className="flex flex-wrap items-center gap-1 rounded-xl bg-slate-100 p-1">
          {(['dashboard','chat','forecast','alerts','advisory','historical'] as const).map((item) => <button key={item} type="button" aria-current={page === item ? 'page' : undefined} onClick={() => onNavigate(item)} className={`rounded-lg px-2 py-2 text-sm font-medium transition sm:px-3 ${page === item ? 'bg-white text-ink shadow-sm' : 'text-muted hover:text-ink'}`}>{t(language, item[0].toUpperCase() + item.slice(1))}</button>)}
        </nav><label className="sr-only" htmlFor="language-select">Language</label><select id="language-select" aria-label="Language" value={language} onChange={(event) => setLanguage(event.target.value as Language)} className="rounded-lg border border-line bg-white px-2 py-2 text-sm"><option value="en">{LANGUAGE_LABELS.en}</option><option value="mr">{LANGUAGE_LABELS.mr}</option><option value="hi">{LANGUAGE_LABELS.hi}</option></select></div>
      </div>
    </header>
  );
}
