import { createContext, ReactNode, useCallback, useContext, useMemo, useState } from "react";
import { ApiError, errorMessage } from "../api/client";
import { getMyStores, getMySeller, SellerOut, StoreOut } from "../api/seller";

// Seller ka account aur uski dukaan, saare seller screens me ek hi baar load hokar baant di jaati hai.
type Ctx = {
  seller: SellerOut | null;
  store: StoreOut | null; // abhi ek hi dukaan sambhalte hain (pehli)
  loading: boolean;
  notSeller: boolean; // abhi apply nahi kiya
  error: string;
  reload: () => Promise<void>;
  setStore: (s: StoreOut) => void;
};

const SellerCtx = createContext<Ctx | null>(null);

export function SellerProvider({ children }: { children: ReactNode }) {
  const [seller, setSeller] = useState<SellerOut | null>(null);
  const [store, setStore] = useState<StoreOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [notSeller, setNotSeller] = useState(false);
  const [error, setError] = useState("");

  const reload = useCallback(async () => {
    setError("");
    try {
      const s = await getMySeller();
      // Dukaan sirf ACTIVE seller ki hoti hai; baaki me list khali hi rahegi
      const stores = s.status === "ACTIVE" ? await getMyStores() : [];
      // State ek saath update karo; ACTIVE status dekhkar store request poori hone se
      // pehle store setup route par na bheje.
      setSeller(s);
      setStore(stores[0] ?? null);
      setNotSeller(false);
    } catch (e) {
      if (e instanceof ApiError && e.code === "NOT_A_SELLER") {
        setSeller(null);
        setStore(null);
        setNotSeller(true);
      } else {
        setError(errorMessage(e));
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const value = useMemo(
    () => ({ seller, store, loading, notSeller, error, reload, setStore }),
    [seller, store, loading, notSeller, error, reload],
  );
  return <SellerCtx.Provider value={value}>{children}</SellerCtx.Provider>;
}

export function useSeller() {
  const v = useContext(SellerCtx);
  if (!v) throw new Error("useSeller ko SellerProvider ke andar use karo");
  return v;
}
