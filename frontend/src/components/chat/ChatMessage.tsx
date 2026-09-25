import { CloudSun, UserRound } from 'lucide-react';
import type { ChatMessageRecord } from '../../types/chat';

interface ChatMessageProps {
  message: ChatMessageRecord;
}

function formatTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Time unavailable' : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date);
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';
  return (
    <article className={`flex items-start gap-3 ${isUser ? 'flex-row-reverse' : ''}`} aria-label={isUser ? 'Your message' : 'WeatherGPT response'}>
      <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${isUser ? 'bg-slate-200 text-slate-700' : 'bg-brand text-white'}`}>
        {isUser ? <UserRound size={17} aria-hidden="true" /> : <CloudSun size={18} aria-hidden="true" />}
      </span>
      <div className={`max-w-[88%] rounded-2xl px-4 py-3.5 sm:max-w-[78%] ${isUser ? 'rounded-tr-sm bg-brand text-white' : 'rounded-tl-sm border border-line bg-white text-ink shadow-sm'}`}>
        <p className="whitespace-pre-wrap text-sm leading-6">{message.content}</p>
        {message.response?.source && (
          <div className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 border-t border-slate-200 pt-2.5 text-xs text-muted">
            <span className="font-semibold text-brand">{message.response.intent === 'ALERT' ? 'Official IMD information' : message.response.intent === 'ADVISORY' ? 'WeatherGPT advisory' : 'Verified weather data'}</span>
            {message.response.intent === 'FORECAST' && <span>Forecast</span>}
            <span aria-hidden="true">·</span><span>Source: {message.response.source}</span>
            {message.response.observed_at && <><span aria-hidden="true">·</span><time dateTime={message.response.observed_at}>Observed {formatTime(message.response.observed_at)}</time></>}
          </div>
        )}
      </div>
    </article>
  );
}
