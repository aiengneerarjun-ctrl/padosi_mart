import { useEffect, useState } from "react";
import * as Location from "expo-location";
import { DEFAULT_LOCATION } from "../config";

export type Coords = { lat: number; lng: number; source: "device" | "default" };

// Backend ko 3 decimal tak round karke bhejna behtar hai (privacy)
const round3 = (n: number) => Math.round(n * 1000) / 1000;

export function useDeviceCoords(enabled: boolean): Coords | null {
  const [coords, setCoords] = useState<Coords | null>(null);

  useEffect(() => {
    if (!enabled || coords) return;
    (async () => {
      try {
        const { status } = await Location.requestForegroundPermissionsAsync();
        if (status === "granted") {
          const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
          setCoords({ lat: round3(pos.coords.latitude), lng: round3(pos.coords.longitude), source: "device" });
          return;
        }
      } catch {
        // GPS band hai ya error aaya: default location par chale jayenge
      }
      setCoords({ ...DEFAULT_LOCATION, source: "default" });
    })();
  }, [enabled, coords]);

  return coords;
}