import { api } from "./client";
import type { StoreCategoryCode } from "../lib/storeCategories";

export type StoreType = "KIRANA" | "RESTAURANT";

export type StoreBrief = {
  id: string;
  name: string;
  store_type: StoreType;
  store_category: StoreCategoryCode;
  image_medium_url: string | null;
  cuisine: string | null;
};

export type StoreCard = StoreBrief & {
  description: string | null;
  distance_km: number;
  eta_minutes: number;
  min_order_amount: number;
};

export type StoreDetail = StoreCard & {
  address: string;
  shop_status: "OPEN" | "CLOSED";
  deliverable: boolean;
  can_order: boolean;
};

export type StoreCategory = { id: string; name: string; product_count: number };

export type ProductCard = {
  id: string;
  name: string;
  selling_unit: string;
  mrp: number;
  selling_price: number;
  discount_percent: number;
  image_thumb_url: string | null;
  image_medium_url: string | null;
  brand_name: string | null;
  only_left: number | null;
  distance_km: number;
  eta_minutes: number;
  store: StoreBrief;
};

export type ProductImage = {
  id: string;
  position: number;
  thumb_url: string;
  medium_url: string;
  large_url: string;
  width: number;
  height: number;
};

export type ProductDetail = ProductCard & {
  description: string | null;
  category_id: string;
  images: ProductImage[];
};

export type Suggestions = { products: string[]; stores: StoreBrief[] };

export type Geo = { lat: number; lng: number };

export const nearbyStores = (p: Geo & { store_type?: StoreType; store_category?: StoreCategoryCode; q?: string; limit?: number; offset?: number }) =>
  api<StoreCard[]>("/shop/stores", { auth: false, query: p });

export const listProducts = (
  p: Geo & {
    store_type?: StoreType;
    q?: string;
    limit?: number;
    offset?: number;
    store_id?: string;
    category_id?: string;
  },
) => api<ProductCard[]>("/shop/products", { auth: false, query: p });

export const suggest = (p: Geo & { q: string }) => api<Suggestions>("/shop/suggest", { auth: false, query: p });

export const fetchStore = (id: string, geo: Geo) => api<StoreDetail>(`/shop/stores/${id}`, { auth: false, query: geo });

export const fetchStoreCategories = (id: string, geo: Geo) =>
  api<StoreCategory[]>(`/shop/stores/${id}/categories`, { auth: false, query: geo });

export const fetchProduct = (id: string, geo: Geo) =>
  api<ProductDetail>(`/shop/products/${id}`, { auth: false, query: geo });
