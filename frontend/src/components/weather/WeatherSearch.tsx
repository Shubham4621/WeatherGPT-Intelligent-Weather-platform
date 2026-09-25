import { Search } from 'lucide-react';
import type { FormEvent } from 'react';
import { t, useLanguage } from '../../i18n';

interface WeatherSearchProps {
  city: string;
  loading: boolean;
  onCityChange: (city: string) => void;
  onSearch: () => void;
}

export default function WeatherSearch({ city, loading, onCityChange, onSearch }: WeatherSearchProps) {
  const { language } = useLanguage();
  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSearch();
  }

  return (
    <form onSubmit={handleSubmit} className="flex w-full flex-col gap-3 sm:flex-row" role="search">
      <label htmlFor="city-search" className="sr-only">{t(language, 'Search weather by city')}</label>
      <div className="relative min-w-0 flex-1">
        <Search className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-muted" size={19} aria-hidden="true" />
        <input
          id="city-search"
          name="city"
          type="search"
          autoComplete="address-level2"
          placeholder={`${t(language, 'Search')} · Dhule`}
          value={city}
          onChange={(event) => onCityChange(event.target.value)}
          disabled={loading}
          className="h-14 w-full rounded-xl border border-line bg-white pl-12 pr-4 text-base text-ink outline-none transition placeholder:text-slate-400 focus:border-brand focus:ring-4 focus:ring-blue-100 disabled:bg-slate-50"
        />
      </div>
      <button
        type="submit"
        disabled={loading || !city.trim()}
        className="inline-flex h-14 items-center justify-center gap-2 rounded-xl bg-brand px-6 font-semibold text-white shadow-sm transition hover:bg-brand-dark focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:cursor-not-allowed disabled:opacity-60 sm:min-w-36"
      >
        {loading ? <><span className="loading-dot" aria-hidden="true" /> {t(language, 'Searching')}</> : <><Search size={17} aria-hidden="true" /> {t(language, 'Search')}</>}
      </button>
    </form>
  );
}
