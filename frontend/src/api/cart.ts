import { api } from "./client";
import { Geo } from "./shop";

export type CartItemOut = {
  product_id: string;
  name: string;
  selling_unit: string;
  mrp: number;
  selling_price: number;
  quantity: number;
  line_total: number;
  image_thumb_url: string | null;
  available: boolean;
  unavailable_reason: string | null; // PRODUCT_INACTIVE / STORE_CLOSED / SELLER_INACTIVE / NOT_DELIVERABLE / OUT_OF_STOCK / LOW_STOCK
  stock_left: number;
};

export type CartStoreGroup = {
  store_id: string;
  store_name: string;
  store_type: string;
  store_category: import("../lib/storeCategories").StoreCategoryCode;
  image_medium_url: string | null;
  store_address: string;
  distance_km: number;
  items: CartItemOut[];
  subtotal: number;
};

export type CartOut = {
  stores: CartStoreGroup[];
  item_count: number;
  subtotal: number;
  max_store_gap_km: number;
  has_problems: boolean;
};

export const getCart = (g: Geo) => api<CartOut>("/cart", { query: g });

// Quantity SET hoti hai (add ya badalna, dono yahi). 1 se 20 tak.
export const putCartItem = (productId: string, quantity: number, g: Geo) =>
  api<CartOut>(`/cart/items/${productId}`, { method: "PUT", body: { quantity, lat: g.lat, lng: g.lng } });

export const deleteCartItem = (productId: string, g: Geo) =>
  api<CartOut>(`/cart/items/${productId}`, { method: "DELETE", query: g });

export const clearCartApi = () => api<void>("/cart", { method: "DELETE" });
