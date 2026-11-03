import { createContext, ReactNode, useContext, useEffect, useMemo, useState } from "react";
import { favProducts, favStores, setFavProduct, setFavStore } from "../api/favourites";
import { useAuth } from "../auth/AuthContext";
import { useCoords } from "../lib/LocationContext";

type Ctx = {
  isStoreFav: (id: string) => boolean;
  isProductFav: (id: string) => boolean;
  toggleStore: (id: string) => Promise<void>;
  toggleProduct: (id: string) => Promise<void>;
};

const FavCtx = createContext<Ctx | null>(null);

type SetUpdater = (f: (s: Set<string>) => Set<string>) => void;

export function FavouritesProvider({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const coords = useCoords();
  const lat = coords?.lat;
  const lng = coords?.lng;

  const [stores, setStores] = useState<Set<string>>(new Set());
  const [products, setProducts] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (status !== "signedIn") {
      setStores(new Set());
      setProducts(new Set());
      return;
    }
    if (lat == null || lng == null) return;
    (async () => {
      try {
        const [s, p] = await Promise.all([favStores({ lat, lng }), favProducts({ lat, lng })]);
        setStores(new Set(s.map((x) => x.id)));
        setProducts(new Set(p.map((x) => x.id)));
      } catch {
        // favourites na aaye to bhi app chalta rahe
      }
    })();
  }, [status, lat, lng]);

  // Pehle screen par turant badal do, phir server ko batao. Fail ho to wapas palat do.
  const flip = async (
    id: string,
    current: Set<string>,
    update: SetUpdater,
    call: (id: string, on: boolean) => Promise<void>,
  ) => {
    const on = !current.has(id);
    const apply = (value: boolean) =>
      update((prev) => {
        const next = new Set(prev);
        value ? next.add(id) : next.delete(id);
        return next;
      });
    apply(on);
    try {
      await call(id, on);
    } catch {
      apply(!on);
    }
  };

  const value = useMemo<Ctx>(
    () => ({
      isStoreFav: (id) => stores.has(id),
      isProductFav: (id) => products.has(id),
      toggleStore: (id) => flip(id, stores, setStores, setFavStore),
      toggleProduct: (id) => flip(id, products, setProducts, setFavProduct),
    }),
    [stores, products],
  );

  return <FavCtx.Provider value={value}>{children}</FavCtx.Provider>;
}

export function useFavourites() {
  const v = useContext(FavCtx);
  if (!v) throw new Error("useFavourites ko FavouritesProvider ke andar use karo");
  return v;
}