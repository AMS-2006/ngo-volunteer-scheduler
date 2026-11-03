import { useEffect } from "react";
import { MapContainer, Marker, Popup, TileLayer, useMap, useMapEvents } from "react-leaflet";
import L from "leaflet";
import { useTranslation } from "react-i18next";
import { Input } from "@/components/ui/input";
import { PLACES } from "@/lib/format";
import { selectCls } from "@/components/shared";

const pin = (color: string) => L.divIcon({
  className: "vc-marker",
  html: `<div style="width:22px;height:22px;border-radius:50% 50% 50% 0;transform:rotate(-45deg);background:${color};border:3px solid #fff;box-shadow:0 2px 6px rgba(15,23,42,.35)"></div>`,
  iconSize: [22, 22], iconAnchor: [11, 22],
});
const BLUE = pin("#0284C7");
const RED = pin("#E11D48");
const BLR: [number, number] = [12.9716, 77.5946];

export interface MapMarker { id: string; lat: number; lng: number; label: string; urgent?: boolean; onClick?: () => void }

function Fit({ markers }: { markers: MapMarker[] }) {
  const map = useMap();
  useEffect(() => {
    if (markers.length > 1) map.fitBounds(L.latLngBounds(markers.map((m) => [m.lat, m.lng])), { padding: [30, 30], maxZoom: 14 });
    else if (markers.length === 1) map.setView([markers[0].lat, markers[0].lng], 14);
  }, [markers, map]);
  return null;
}

export function MapView({ markers, height = 360 }: { markers: MapMarker[]; height?: number }) {
  return (
    <div data-testid="map-view" className="relative z-0 overflow-hidden rounded-xl border border-slate-200 shadow-sm" style={{ height }}>
      <MapContainer center={BLR} zoom={11} scrollWheelZoom={false} style={{ height: "100%", width: "100%" }}>
        <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        {markers.map((m) => (
          <Marker key={m.id} position={[m.lat, m.lng]} icon={m.urgent ? RED : BLUE} eventHandlers={m.onClick ? { click: m.onClick } : undefined}>
            <Popup>{m.label}</Popup>
          </Marker>
        ))}
        <Fit markers={markers} />
      </MapContainer>
    </div>
  );
}

function ClickSetter({ onPick }: { onPick: (lat: number, lng: number) => void }) {
  useMapEvents({ click: (e) => onPick(Number(e.latlng.lat.toFixed(5)), Number(e.latlng.lng.toFixed(5))) });
  return null;
}

/** Location name + preset city/area + click-to-pin on an OpenStreetMap map. */
export function LocationPicker({ location, lat, lng, onChange, testId = "location" }: {
  location: string; lat: number | null; lng: number | null; testId?: string;
  onChange: (v: { location: string; latitude: number | null; longitude: number | null }) => void;
}) {
  const { t } = useTranslation();
  const markers: MapMarker[] = lat != null && lng != null ? [{ id: "pick", lat, lng, label: location }] : [];
  return (
    <div className="space-y-2">
      <div className="grid gap-2 sm:grid-cols-2">
        <Input data-testid={`${testId}-input`} value={location} placeholder={t("common.location")}
          onChange={(e) => onChange({ location: e.target.value, latitude: lat, longitude: lng })} />
        <select data-testid={`${testId}-preset`} className={selectCls} value=""
          onChange={(e) => { const p = PLACES.find((x) => x.name === e.target.value); if (p) onChange({ location: p.name, latitude: p.lat, longitude: p.lng }); }}>
          <option value="">— {t("common.location")} —</option>
          {PLACES.map((p) => <option key={p.name} value={p.name}>{p.name}</option>)}
        </select>
      </div>
      <div className="relative z-0 overflow-hidden rounded-xl border border-slate-200" style={{ height: 220 }}>
        <MapContainer center={lat != null && lng != null ? [lat, lng] : BLR} zoom={11} style={{ height: "100%", width: "100%" }}>
          <TileLayer attribution="&copy; OpenStreetMap" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          {markers.map((m) => <Marker key={m.id} position={[m.lat, m.lng]} icon={BLUE} />)}
          <ClickSetter onPick={(la, ln) => onChange({ location, latitude: la, longitude: ln })} />
          <Fit markers={markers} />
        </MapContainer>
      </div>
      <p className="text-xs text-slate-500">{t("common.pickOnMap")} {lat != null && lng != null && <span data-testid={`${testId}-coords`}>({lat.toFixed(3)}, {lng?.toFixed(3)})</span>}</p>
    </div>
  );
}
