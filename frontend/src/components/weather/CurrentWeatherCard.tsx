import { Cloud, CloudSun, Compass, Droplets, Eye, Gauge, Sun, Wind } from 'lucide-react';
import type { WeatherResponse } from '../../types/weather';
import MetricCard from './MetricCard';
import { conditionLabel, localeFor, t, useLanguage } from '../../i18n';

interface CurrentWeatherCardProps {
  data: WeatherResponse;
}

function degrees(value: number | null): string {
  if (value === null) return '—';
  const directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
  return directions[Math.round(value / 45) % 8];
}

export default function CurrentWeatherCard({ data }: CurrentWeatherCardProps) {
  const { language } = useLanguage();
  const { location, weather } = data;
  const iconUrl = weather.icon ? `https://openweathermap.org/img/wn/${encodeURIComponent(weather.icon)}@2x.png` : null;

  return (
    <section aria-labelledby="current-weather-heading" className="space-y-5" aria-live="polite">
      <div className="weather-hero overflow-hidden rounded-3xl border border-line p-6 shadow-card sm:p-9">
        <div className="flex flex-col justify-between gap-7 sm:flex-row sm:items-start">
          <div>
            <p className="flex items-center gap-2 text-sm font-semibold text-brand"><span className="h-2 w-2 rounded-full bg-emerald-500" /> LIVE WEATHER · {t(language, 'Current conditions')}</p>
            <h2 id="current-weather-heading" className="mt-4 text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
              {location.name}<span className="ml-2 text-muted">{location.country}</span>
            </h2>
            <p className="mt-1 text-sm text-muted">
              {Math.abs(location.latitude).toFixed(2)}° {location.latitude < 0 ? 'S' : 'N'}, {Math.abs(location.longitude).toFixed(2)}° {location.longitude < 0 ? 'W' : 'E'}
            </p>
            <p className="mt-6 max-w-xl text-base font-medium capitalize text-ink">{conditionLabel(language, weather.description)}</p>
            <p className="mt-2 text-sm text-muted">{t(language, 'Feels like')} {weather.feels_like.toFixed(1)}°</p>
          </div>
          <div className="flex items-center gap-4 sm:flex-col sm:items-end sm:gap-0">
            {iconUrl ? <img src={iconUrl} alt="" className="h-20 w-20 object-contain sm:h-24 sm:w-24" /> : <CloudSun aria-hidden="true" className="h-16 w-16 text-amber-200 sm:h-20 sm:w-20" strokeWidth={1.3} />}
            <p className="text-6xl font-light tracking-tighter text-brand sm:text-7xl">{Math.round(weather.temperature)}<span className="align-top text-3xl">°</span></p>
            <p className="mt-1 text-sm text-muted">H {Math.round(weather.temp_max)}° <span className="mx-1 text-slate-400">/</span> L {Math.round(weather.temp_min)}°</p>
          </div>
        </div>
        <div className="mt-7 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4 text-xs text-muted">
          <span>{t(language, 'Observed')} {new Intl.DateTimeFormat(localeFor(language), { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(data.observed_at))}</span>
          <span>{t(language, 'Source')}: {data.source}</span>
        </div>
      </div>

      <div>
        <div className="mb-3 flex items-center gap-2"><Sun className="text-brand" size={18} aria-hidden="true" /><h2 className="text-base font-semibold text-ink">{t(language, 'Weather details')}</h2></div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 lg:grid-cols-4">
          <MetricCard label={t(language, 'Humidity')} value={String(weather.humidity)} unit="%" icon={Droplets} detail={t(language, 'Relative humidity')} />
          <MetricCard label={t(language, 'Wind speed')} value={weather.wind_speed.toFixed(1)} unit="m/s" icon={Wind} detail={weather.wind_gust == null ? t(language, 'Current wind') : `${t(language, 'Gusts')} ${weather.wind_gust.toFixed(1)} m/s`} />
          <MetricCard label={t(language, 'Wind direction')} value={degrees(weather.wind_direction)} unit={weather.wind_direction == null ? '' : `${weather.wind_direction}°`} icon={Compass} detail={t(language, 'Direction wind is coming from')} />
          <MetricCard label={t(language, 'Pressure')} value={String(weather.pressure)} unit="hPa" icon={Gauge} detail={t(language, 'Sea-level pressure')} />
          <MetricCard label={t(language, 'Visibility')} value={weather.visibility == null ? '—' : (weather.visibility / 1000).toFixed(1)} unit={weather.visibility == null ? '' : 'km'} icon={Eye} detail={t(language, 'Horizontal visibility')} />
          <MetricCard label={t(language, 'Cloud cover')} value={weather.cloudiness == null ? '—' : String(weather.cloudiness)} unit={weather.cloudiness == null ? '' : '%'} icon={Cloud} detail={t(language, 'Sky coverage')} />
        </div>
      </div>

      <section aria-label="Sun times and data availability" className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-2xl border border-line bg-white p-4 shadow-sm"><p className="text-xs font-medium text-muted">{t(language, 'Sunrise')}</p><p className="mt-1 text-sm font-semibold text-ink">{new Intl.DateTimeFormat(localeFor(language), { timeStyle: 'short' }).format(new Date(data.sun.sunrise))}</p></div>
        <div className="rounded-2xl border border-line bg-white p-4 shadow-sm"><p className="text-xs font-medium text-muted">{t(language, 'Sunset')}</p><p className="mt-1 text-sm font-semibold text-ink">{new Intl.DateTimeFormat(localeFor(language), { timeStyle: 'short' }).format(new Date(data.sun.sunset))}</p></div>
        <div className="rounded-2xl border border-dashed border-line bg-white/60 p-4"><p className="text-xs font-medium text-muted">{t(language, 'Rain probability')}</p><p className="mt-1 text-sm font-semibold text-muted">{t(language, 'Rain probability unavailable')}</p></div>
      </section>
    </section>
  );
}
