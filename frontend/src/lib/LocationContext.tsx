import { createContext, ReactNode, useContext } from "react";
import { Coords, useDeviceCoords } from "./location";

const Ctx = createContext<Coords | null>(null);

export function LocationProvider({ enabled, children }: { enabled: boolean; children: ReactNode }) {
  const coords = useDeviceCoords(enabled);
  return <Ctx.Provider value={coords}>{children}</Ctx.Provider>;
}

export const useCoords = () => useContext(Ctx);