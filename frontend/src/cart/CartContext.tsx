import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { clearCartApi, CartOut, deleteCartItem, getCart, putCartItem } from "../api/cart";
import { errorMessage } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useCoords } from "../lib/LocationContext";

type Ctx = {
  cart: CartOut | null;
  loading: boolean;
  itemCount: number;
  qtyOf: (productId: string) => number;
  isBusy: (productId: string) => boolean;
  // Error ho to message wapas aata hai, sab theek ho to null
  setQty: (productId: string, qty: number) => Promise<string | null>;
  clear: () => Promise<string | null>;
  refresh: () => Promise<void>;
};

const CartCtx = createContext<Ctx | null>(null);

export function CartProvider({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const coords = useCoords();
  const lat = coords?.lat;
  const lng = coords?.lng;

  const [cart, setCart] = useState<CartOut | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState<Set<string>>(new Set());

  const refresh = useCallback(async () => {
    if (status !== "signedIn" || lat == null || lng == null) return;
    setLoading(true);
    try {
      setCart(await getCart({ lat, lng }));
    } catch {
      // cart na aaye to bhi app chalta rahe
    } finally {
      setLoading(false);
    }
  }, [status, lat, lng]);

  useEffect(() => {
    if (status !== "signedIn") {
      setCart(null);
      return;
    }
    refresh();
  }, [status, refresh]);

  const qtyMap = useMemo(() => {
    const m = new Map<string, number>();
    cart?.stores.forEach((s) => s.items.forEach((i) => m.set(i.product_id, i.quantity)));
    return m;
  }, [cart]);

  const setQty = useCallback(
    async (productId: string, qty: number): Promise<string | null> => {
      if (lat == null || lng == null) return "Location abhi mili nahi, thodi der baad try karein.";
      setBusy((p) => new Set(p).add(productId));
      try {
        const geo = { lat, lng };
        const next = qty <= 0 ? await deleteCartItem(productId, geo) : await putCartItem(productId, qty, geo);
        setCart(next);
        return null;
      } catch (e) {
        return errorMessage(e);
      } finally {
        setBusy((p) => {
          const n = new Set(p);
          n.delete(productId);
          return n;
        });
      }
    },
    [lat, lng],
  );

  const clear = useCallback(async (): Promise<string | null> => {
    try {
      await clearCartApi();
      await refresh();
      return null;
    } catch (e) {
      return errorMessage(e);
    }
  }, [refresh]);

  const value = useMemo<Ctx>(
    () => ({
      cart,
      loading,
      itemCount: cart?.item_count ?? 0,
      qtyOf: (id) => qtyMap.get(id) ?? 0,
      isBusy: (id) => busy.has(id),
      setQty,
      clear,
      refresh,
    }),
    [cart, loading, qtyMap, busy, setQty, clear, refresh],
  );

  return <CartCtx.Provider value={value}>{children}</CartCtx.Provider>;
}

export function useCart() {
  const v = useContext(CartCtx);
  if (!v) throw new Error("useCart ko CartProvider ke andar use karo");
  return v;
}