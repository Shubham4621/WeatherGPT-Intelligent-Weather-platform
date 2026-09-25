export default function TypingIndicator() {
  return (
    <div className="flex items-start gap-3" role="status" aria-label="WeatherGPT is preparing a response">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand text-xs font-bold text-white">W</span>
      <div className="rounded-2xl rounded-tl-sm border border-line bg-white px-4 py-3 shadow-sm">
        <span className="flex gap-1.5" aria-hidden="true"><i className="typing-dot" /><i className="typing-dot delay-1" /><i className="typing-dot delay-2" /></span>
        <span className="sr-only">Getting current weather data</span>
      </div>
    </div>
  );
}
