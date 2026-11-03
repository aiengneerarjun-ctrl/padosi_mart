import { File } from "expo-file-system";
import { api } from "./client";

export type ProductStatus = "PENDING_APPROVAL" | "ACTIVE" | "OUT_OF_STOCK" | "INACTIVE" | "REJECTED";

export type ProductImage = {
  id: string;
  position: number;
  thumb_url: string;
  medium_url: string;
  large_url: string;
  width: number;
  height: number;
};

export type SellerProduct = {
  id: string;
  store_id: string;
  category_id: string;
  brand_id: string | null;
  sku: string;
  barcode: string | null;
  name: string;
  name_hi: string | null;
  name_bho: string | null;
  description: string | null;
  selling_unit: string;
  commission_mode: "PERCENT" | "FIXED";
  commission_unit: string;
  commission_value: number;
  commission_unit_quantity: number;
  mrp: number;
  selling_price: number;
  discount_percent: number;
  status: ProductStatus;
  status_reason: string | null;
  stock: number;
  low_stock: boolean;
  images: ProductImage[];
  created_at: string;
};

export type Category = { id: string; parent_id: string | null; name: string; sort_order: number };

export type ProductCreateBody = {
  sku: string;
  category_id: string;
  name: string;
  name_hi?: string | null;
  description?: string | null;
  selling_unit: string;
  mrp: string; // string bhejte hain taaki paise me galti na ho
  selling_price: string;
  initial_stock: number;
  low_stock_threshold: number;
};

export type ProductUpdateBody = Partial<
  Omit<ProductCreateBody, "sku" | "initial_stock"> & { mrp: string; selling_price: string }
>;

export type StockReason = "STOCK_IN" | "ADJUSTMENT" | "DAMAGED";

export type StockTransaction = {
  id: string;
  change: number;
  quantity_after: number;
  reason: string;
  note: string | null;
  created_at: string;
};

export const getCategories = () => api<Category[]>("/categories", { auth: false });

export const listProducts = (storeId: string, status: ProductStatus | undefined, limit: number, offset: number) =>
  api<SellerProduct[]>(`/stores/${storeId}/products`, { query: { status, limit, offset } });

export const getProduct = (id: string) => api<SellerProduct>(`/products/${id}`);

export const createProduct = (storeId: string, body: ProductCreateBody) =>
  api<SellerProduct>(`/stores/${storeId}/products`, { method: "POST", body });

export const updateProduct = (id: string, body: ProductUpdateBody) =>
  api<SellerProduct>(`/products/${id}`, { method: "PATCH", body });

export const setProductStatus = (id: string, status: "ACTIVE" | "INACTIVE") =>
  api<SellerProduct>(`/products/${id}/status`, { method: "POST", body: { status } });

export const adjustStock = (id: string, body: { change: number; reason: StockReason; note?: string | null }) =>
  api<SellerProduct>(`/products/${id}/stock`, { method: "POST", body });

export const getStockHistory = (id: string) => api<StockTransaction[]>(`/products/${id}/stock-history`, { query: { limit: 30 } });

export type PickedImage = { uri: string; name?: string | null; mimeType?: string | null };

export function uploadProductImage(productId: string, img: PickedImage) {
  const form = new FormData();
  // Naye Expo ka fetch purana {uri, name, type} tareeka nahi samajhta (chupchap fail hota hai).
  // Isliye file ko expo-file-system ki File ke roop me dete hain, jise wo seedha padh leta hai.
  form.append("file", new File(img.uri) as unknown as Blob);
  return api<SellerProduct>(`/products/${productId}/images`, { method: "POST", body: form, timeoutMs: 60000 });
}

export const deleteProductImage = (productId: string, imageId: string) =>
  api<SellerProduct>(`/products/${productId}/images/${imageId}`, { method: "DELETE" });

export const reorderProductImages = (productId: string, image_ids: string[]) =>
  api<SellerProduct>(`/products/${productId}/images/order`, { method: "PUT", body: { image_ids } });
