import { useEffect } from 'react';
import { CircleMarker, MapContainer, Polyline, Popup, TileLayer, useMap, useMapEvents } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import type { NwpForecastResponse, NwpPoint, ResolvedLocation } from '../../services/weatherApi';
import type { WeatherAlertsResponse, WeatherResponse } from '../../types/weather';

interface WeatherMapCanvasProps {
  location: ResolvedLocation | null;
  current: WeatherResponse | null;
  alerts: WeatherAlertsResponse | null;
  showAlerts: boolean;
  nwp: NwpForecastResponse | null;
  nwpPoint: NwpPoint | null;
  showNwp: boolean;
  showPrecipitation: boolean;
  showWind: boolean;
  onMapSelect: (latitude: number, longitude: number) => void;
  onTileError: () => void;
  onTileLoad: () => void;
  station?: { station_id: string; station_name: string; latitude: number; longitude: number; elevation_m: number | null; source: string; coordinate_precision?: string | null } | null;
}

function MapLocationSync({ location }: { location: ResolvedLocation | null }) {
  const map = useMap();
  useEffect(() => {
    if (location) map.flyTo([location.latitude, location.longitude], Math.max(map.getZoom(), 8), { duration: 0.5 });
  }, [location, map]);
  return null;
}

function MapClickSelect({ onSelect }: { onSelect: (latitude: number, longitude: number) => void }) {
  useMapEvents({ click: (event) => onSelect(event.latlng.lat, event.latlng.lng) });
  return null;
}

export default function WeatherMapCanvas({ location, current, alerts, showAlerts, nwp, nwpPoint, showNwp, showPrecipitation, showWind, onMapSelect, onTileError, onTileLoad, station = null }: WeatherMapCanvasProps) {
  const activeWarnings = alerts?.forecast_days.filter((day) => day.is_active) ?? [];
  return <div className="relative h-[360px] min-h-[360px] w-full overflow-hidden rounded-2xl sm:h-[480px] sm:min-h-[480px]" role="region" aria-label="Interactive geographic weather map">
    <MapContainer center={[20.5937, 78.9629]} zoom={4} minZoom={2} maxZoom={18} scrollWheelZoom className="h-full w-full" keyboard>
      <TileLayer url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="&copy; <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap contributors</a>" maxZoom={19} eventHandlers={{ tileerror: onTileError, load: onTileLoad }} />
      <MapLocationSync location={location}/>
      <MapClickSelect onSelect={onMapSelect}/>
      {location && <CircleMarker center={[location.latitude, location.longitude]} radius={9} pathOptions={{ color: '#075985', fillColor: '#38bdf8', fillOpacity: 0.9, weight: 3 }}>
        <Popup><div className="min-w-48 space-y-1 text-sm"><strong>{location.city ?? location.query}</strong><div>{location.latitude.toFixed(5)}, {location.longitude.toFixed(5)}</div><div>Location source: {location.source}</div>{current ? <div className="border-t pt-1">{current.weather.temperature.toFixed(1)} °C · {current.weather.description}<br/>Wind {current.weather.wind_speed.toFixed(1)} m/s · Humidity {current.weather.humidity}%<br/>Weather source: {current.source}</div> : <div>Current weather unavailable.</div>}</div></Popup>
      </CircleMarker>}
      {station && <CircleMarker center={[station.latitude, station.longitude]} radius={8} pathOptions={{ color: '#15803d', fillColor: '#4ade80', fillOpacity: 0.95, weight: 3 }}>
        <Popup><div className="min-w-48 space-y-1 text-sm"><strong>IMD Station · {station.station_name}</strong><div>Station ID: {station.station_id}</div><div>{station.latitude.toFixed(5)}, {station.longitude.toFixed(5)}{station.elevation_m != null ? ` · ${station.elevation_m} m MSL` : ''}</div>{station.coordinate_precision && <div>Coordinate metadata: {station.coordinate_precision}</div>}<div>Source: {station.source}</div></div></Popup>
      </CircleMarker>}
      {location && showAlerts && alerts && activeWarnings.length > 0 && <CircleMarker center={[location.latitude, location.longitude]} radius={15} pathOptions={{ color: '#c2410c', fillColor: '#fb923c', fillOpacity: 0, weight: 3 }}>
        <Popup><div className="min-w-48 space-y-1 text-sm"><strong>OFFICIAL IMD WARNING · district lookup</strong><div>{alerts.district}, {alerts.state}</div>{activeWarnings.map((day) => <div key={day.date}>{new Date(day.date).toLocaleDateString()}: {day.warnings.map((warning) => warning.warning_type).join(', ')} · IMD level {day.severity ?? 'not specified'}</div>)}<div>Source: {alerts.source}</div><div>Marker denotes the selected city lookup only; no warning boundary geometry was supplied.</div></div></Popup>
      </CircleMarker>}
      {showNwp && nwp?.selected_grid_point && nwpPoint && <>
        <Polyline positions={[[location?.latitude ?? nwp.selected_grid_point.latitude, location?.longitude ?? nwp.selected_grid_point.longitude], [nwp.selected_grid_point.latitude, nwp.selected_grid_point.longitude]]} pathOptions={{ color: '#7c3aed', dashArray: '5 7', weight: 2 }}/>
        <CircleMarker center={[nwp.selected_grid_point.latitude, nwp.selected_grid_point.longitude]} radius={8} pathOptions={{ color: '#6d28d9', fillColor: '#a78bfa', fillOpacity: 0.95, weight: 3 }}>
          <Popup><div className="min-w-48 space-y-1 text-sm"><strong>NWP model grid point</strong><div>{nwp.selected_grid_point.latitude.toFixed(3)}, {nwp.selected_grid_point.longitude.toFixed(3)}</div><div>{nwp.selected_grid_point.distance_km.toFixed(2)} km from requested point · {nwp.resolution_degrees}°</div><div>Valid: {new Date(nwpPoint.forecast_time).toUTCString()}</div>{nwpPoint.temperature_c != null && <div>Temperature: {nwpPoint.temperature_c.toFixed(1)} °C</div>}{showPrecipitation && nwpPoint.precipitation_since_initialization_mm != null && <div>Accumulated precipitation since run: {nwpPoint.precipitation_since_initialization_mm.toFixed(2)} mm</div>}{showWind && nwpPoint.wind_speed_ms != null && <div>10 m wind speed: {nwpPoint.wind_speed_ms.toFixed(1)} m/s</div>}<div>Source: {nwp.source} · {nwp.model}</div></div></Popup>
        </CircleMarker>
      </>}
    </MapContainer>
  </div>;
}
