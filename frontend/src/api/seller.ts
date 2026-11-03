import { api } from "./client";
import type { StoreCategoryCode } from "../lib/storeCategories";
import { File } from "expo-file-system";

export type SellerType = "KIRANA" | "RESTAURANT";

export type SellerOut = {
  id: string;
  seller_type: SellerType;
  store_category: StoreCategoryCode;
  store_image_medium_url: string | null;
  business_name: string;
  owner_name: string;
  status: "PENDING" | "ACTIVE" | "REJECTED" | "SUSPENDED";
  status_reason: string | null;
  created_at: string;
};

export const applySeller = (body: { seller_type: SellerType; store_category: StoreCategoryCode; business_name: string; owner_name: string }) =>
  api<SellerOut>("/sellers/apply", { method: "POST", body });

export function uploadSellerStoreImage(uri: string) {
  const form = new FormData();
  form.append("file", new File(uri) as unknown as Blob);
  return api<SellerOut>("/sellers/me/store-image", { method: "POST", body: form, timeoutMs: 60000 });
}

// Apply na kiya ho to backend 403 NOT_A_SELLER deta hai
export const getMySeller = () => api<SellerOut>("/sellers/me");

// ---------------- Dukaan (store) ----------------

export type ShopStatus = "OPEN" | "CLOSED";

export type StoreOut = {
  id: string;
  store_type: SellerType;
  store_category: StoreCategoryCode;
  image_medium_url: string | null;
  name: string;
  description: string | null;
  cuisine: string | null;
  address: string;
  latitude: number;
  longitude: number;
  delivery_radius_km: number;
  min_order_amount: number;
  shop_status: ShopStatus;
  created_at: string;
};

export type StoreBody = {
  store_category: StoreCategoryCode;
  name: string;
  description?: string | null;
  cuisine?: string | null;
  address: string;
  latitude: number;
  longitude: number;
  delivery_radius_km: number;
  min_order_amount: number;
};

export const getMyStores = () => api<StoreOut[]>("/stores/mine");
export const createStore = (body: StoreBody) => api<StoreOut>("/stores", { method: "POST", body });
export function uploadStoreImage(storeId: string, uri: string) {
  const form = new FormData();
  form.append("file", new File(uri) as unknown as Blob);
  return api<StoreOut>(`/stores/${storeId}/image`, { method: "POST", body: form, timeoutMs: 60000 });
}
export const updateStore = (id: string, body: Partial<StoreBody>) =>
  api<StoreOut>(`/stores/${id}`, { method: "PATCH", body });
export const setShopStatus = (id: string, status: ShopStatus) =>
  api<StoreOut>(`/stores/${id}/status`, { method: "POST", body: { status } });
