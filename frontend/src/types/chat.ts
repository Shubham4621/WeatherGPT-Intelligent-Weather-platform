import type { CurrentWeather } from './weather';

export type ChatIntent = 'CURRENT_WEATHER' | 'FORECAST' | 'ALERT' | 'ADVISORY' | 'HISTORICAL_WEATHER' | 'UNKNOWN';

export interface ChatResponse {
  message: string;
  intent: ChatIntent;
  location: string | null;
  source: string | null;
  tool_used: string | null;
  observed_at: string | null;
  weather: CurrentWeather | null;
  forecast?: import('./weather').ForecastDay[] | null;
  alert_days?: import('./weather').AlertDay[] | null;
  advisory?: import('./weather').WeatherAdvisory | null;
}

export interface ChatMessageRecord {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  response?: ChatResponse;
}
