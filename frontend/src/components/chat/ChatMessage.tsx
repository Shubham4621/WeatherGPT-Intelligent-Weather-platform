import { AlertTriangle, CloudSun, Droplets, Gauge, UserRound, Wind } from 'lucide-react';
import type { ChatMessageRecord } from '../../types/chat';
import VoiceOutput from '../voice/VoiceOutput';

interface ChatMessageProps {
  message: ChatMessageRecord;
}

function formatTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Time unavailable' : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date);
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';
  const response = message.response;
  const activeAlerts = response?.alert_days?.filter((day) => day.is_active) ?? [];
  return (
    <article className={`flex items-start gap-3 ${isUser ? 'flex-row-reverse' : ''}`} aria-label={isUser ? 'Your message' : 'WeatherGPT response'}>
      <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${isUser ? 'bg-slate-200 text-slate-700' : 'bg-brand text-white'}`}>
        {isUser ? <UserRound size={17} aria-hidden="true" /> : <CloudSun size={18} aria-hidden="true" />}
      </span>
      <div className={`max-w-[88%] rounded-2xl px-4 py-3.5 sm:max-w-[78%] ${isUser ? 'rounded-tr-sm bg-brand text-white' : 'rounded-tl-sm border border-line bg-white text-ink shadow-sm'}`}>
        <p className="whitespace-pre-wrap text-sm leading-6">{message.content}</p>
        {!isUser && response?.weather && <section aria-label="Current weather response details" className="mt-4 grid grid-cols-2 gap-2 rounded-xl border border-line bg-slate-50 p-3 sm:grid-cols-4">
          <WeatherFact icon={CloudSun} label="Temperature" value={`${Math.round(response.weather.temperature)}°C`}/>
          <WeatherFact icon={Droplets} label="Humidity" value={`${response.weather.humidity}%`}/>
          <WeatherFact icon={Wind} label="Wind" value={`${response.weather.wind_speed.toFixed(1)} m/s`}/>
          <WeatherFact icon={Gauge} label="Pressure" value={`${response.weather.pressure} hPa`}/>
        </section>}
        {!isUser && response?.forecast?.length ? <section aria-label="Forecast response cards" className="mt-4 grid gap-2 sm:grid-cols-2">{response.forecast.slice(0, 4).map((day) => <article key={day.date} className="rounded-xl border border-line bg-slate-50 p-3"><p className="text-xs font-semibold text-muted">{new Date(day.date).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric', timeZone: 'UTC' })}</p><p className="mt-1 text-sm font-semibold">{Math.round(day.temperature_max)}° / {Math.round(day.temperature_min)}°C</p><p className="mt-1 text-xs capitalize text-muted">{day.description}</p><div className="mt-2 flex flex-wrap gap-x-3 text-xs text-muted">{day.rain_probability !== null && <span>Rain {Math.round(day.rain_probability)}%</span>}{day.wind_speed !== null && <span>Wind {day.wind_speed.toFixed(1)} m/s</span>}</div></article>)}</section> : null}
        {!isUser && response?.intent === 'ALERT' && <section className="mt-4 rounded-xl border border-amber-300 bg-amber-50 p-3" aria-label="Official IMD warning details"><p className="flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-amber-900"><AlertTriangle size={15}/> Official IMD warning</p>{activeAlerts.length ? activeAlerts.map((day) => <div key={day.date} className="mt-2"><p className="text-sm font-semibold">{day.warnings.map((warning) => warning.warning_type).join(', ')}</p><p className="text-xs text-muted">{new Date(day.date).toLocaleDateString()} · {day.severity ?? 'Severity not specified'}</p></div>) : response.alert_days?.length ? <p className="mt-2 text-xs text-muted">No official warning reported in the returned data for these dates.</p> : <p className="mt-2 text-xs text-muted">Official IMD warning data is unavailable in this response.</p>}</section>}
        {!isUser && response?.advisory && <section className="mt-4 rounded-xl border border-blue-200 bg-blue-50 p-3" aria-label="WeatherGPT advisory details"><p className="text-xs font-bold uppercase tracking-wide text-brand">WeatherGPT advisory · {response.advisory.risk_label}: {response.advisory.risk_level ?? 'Not assessed'}</p>{response.advisory.recommendations[0] && <p className="mt-2 text-sm">{response.advisory.recommendations[0]}</p>}{response.advisory.official_warning && <div className="mt-3 border-t border-amber-300 pt-2 text-xs"><strong>Official IMD information:</strong> {response.advisory.official_warning.warnings.join(', ')} · {response.advisory.official_warning.source}</div>}</section>}
        {response?.source && (
          <div className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 border-t border-slate-200 pt-2.5 text-xs text-muted">
            <span className="font-semibold text-brand">{response.intent === 'ALERT' ? 'Official IMD information' : response.intent === 'ADVISORY' ? 'WeatherGPT advisory' : response.intent === 'FORECAST' ? 'Operational forecast' : 'WeatherGPT data response'}</span>
            <span aria-hidden="true">·</span><span>Source: {response.source}</span>
            {response.observed_at && <><span aria-hidden="true">·</span><time dateTime={response.observed_at}>Observed {formatTime(response.observed_at)}</time></>}
          </div>
        )}
        {!isUser && <VoiceOutput text={message.content} />}
      </div>
    </article>
  );
}

function WeatherFact({ icon: Icon, label, value }: { icon: typeof CloudSun; label: string; value: string }) {
  return <div className="min-w-0"><p className="flex items-center gap-1 text-[10px] text-muted"><Icon size={12}/>{label}</p><p className="mt-1 text-xs font-semibold text-ink">{value}</p></div>;
}
