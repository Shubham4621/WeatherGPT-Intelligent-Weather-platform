export interface WeatherLocation {
  name: string;
  country: string;
  latitude: number;
  longitude: number;
}

export interface CurrentWeather {
  temperature: number;
  feels_like: number;
  temp_min: number;
  temp_max: number;
  humidity: number;
  pressure: number;
  wind_speed: number;
  wind_direction: number | null;
  wind_gust: number | null;
  visibility: number | null;
  cloudiness: number | null;
  description: string;
  icon: string | null;
}

export interface SunInfo {
  sunrise: string;
  sunset: string;
}

export interface WeatherResponse {
  location: WeatherLocation;
  weather: CurrentWeather;
  sun: SunInfo;
  source: string;
  observed_at: string;
}

export interface ForecastDay {
  date: string; temperature_min: number; temperature_max: number; feels_like: number | null;
  humidity: number | null; description: string; cloudiness: number | null; wind_speed: number | null; rain_probability: number | null;
}
export interface ForecastResponse { location: WeatherLocation; forecast: ForecastDay[]; source: string; forecasted_at: string }

export interface AlertWarning { warning_type: string; warning_code: number }
export interface AlertDay { date: string; warnings: AlertWarning[]; warning_codes: number[]; severity: string | null; severity_code: number | null; is_active: boolean }
export interface WeatherAlertsResponse { location: string; district: string; state: string; issued_at: string; forecast_days: AlertDay[]; source: string; source_url: string; provider_status?: 'available'; official?: boolean; retrieved_at?: string | null; reference?: string | null }

export type AdvisoryActivity = 'TRAVEL' | 'OUTDOOR_ACTIVITY' | 'COMMUTE' | 'EXERCISE' | 'EVENT' | 'AGRICULTURE' | 'GENERAL_PRECAUTION';
export interface AdvisoryFactor { code: string; detail: string; source: string }
export interface OfficialWarningSummary { warnings: string[]; severity: string | null; date: string; source: string; source_url: string }
export interface WeatherAdvisory { location: string; date: string | null; activity: AdvisoryActivity; summary: string; risk_level: 'LOW' | 'MODERATE' | 'HIGH' | null; risk_label: string; factors: AdvisoryFactor[]; recommendations: string[]; official_warning: OfficialWarningSummary | null; official_warning_status: string; sources: string[] }
