import * as Location from "expo-location";
import { DEFAULT_LOCATION } from "../config";
import { listProducts, nearbyStores } from "../api/shop";
import { StoreOut } from "../api/seller";

const R = 6371;
const rad = (d: number) => (d * Math.PI) / 180;

// Backend jaisa hi haversine: do jagah ke beech km
export function distanceKm(aLat: number, aLng: number, bLat: number, bLng: number): number {
  const a =
    Math.sin(rad(bLat - aLat) / 2) ** 2 + Math.cos(rad(aLat)) * Math.cos(rad(bLat)) * Math.sin(rad(bLng - aLng) / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(Math.min(1, a)));
}

export type DiagLine = { ok: boolean; text: string };

// Wahi query chalate hain jo customer app chalata hai, aur dekhte hain ki rukawat kahan hai.
export async function diagnoseVisibility(store: StoreOut): Promise<DiagLine[]> {
  const out: DiagLine[] = [];

  // 1) Dukaan ki apni location par (doori 0): seller / dukaan / saman / stock / category ki sab shartein
  const here = { lat: store.latitude, lng: store.longitude };
  const [prods, stores] = await Promise.all([
    listProducts({ ...here, store_id: store.id, limit: 50 }),
    nearbyStores({ ...here, limit: 50 }),
  ]);
  const listed = stores.some((s) => s.id === store.id);
  out.push({
    ok: prods.length > 0,
    text:
      prods.length > 0
        ? `Dukaan ki location par customer ko ${prods.length} saman dikhta hai.`
        : "Dukaan ki location par bhi customer ko koi saman nahi dikhta. Matlab saman abhi bikne layak nahi: admin approve, stock, dukaan khuli, ya category band ho sakti hai. Upar ka checklist dekhein.",
  });
  out.push({
    ok: listed,
    text: listed
      ? "Dukaan customer ki “Paas ki dukaanein” list me aati hai."
      : "Dukaan “Paas ki dukaanein” list me nahi aati (khuli hui aur kam se kam ek live saman wali dukaan hi aati hai).",
  });

  // 2) Is phone ki location se doori
  let me = { ...DEFAULT_LOCATION };
  let source = "default (Barharia)";
  try {
    const perm = await Location.requestForegroundPermissionsAsync();
    if (perm.status === "granted") {
      const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
      me = { lat: pos.coords.latitude, lng: pos.coords.longitude };
      source = "is phone ka GPS";
    }
  } catch {
    // GPS band: default location
  }
  const d = distanceKm(me.lat, me.lng, store.latitude, store.longitude);
  const inside = d <= store.delivery_radius_km;
  out.push({
    ok: inside,
    text: inside
      ? `Customer (${source}) dukaan se ${d.toFixed(1)} km door hai, daayra ${store.delivery_radius_km} km hai. Andar hai.`
      : `Customer (${source}) dukaan se ${d.toFixed(1)} km door hai, par daayra sirf ${store.delivery_radius_km} km hai. Isliye customer ko kuch nahi dikhega. Dukaan ki location ya delivery daayra badlein (Badlein dabayein).`,
  });
  return out;
}
