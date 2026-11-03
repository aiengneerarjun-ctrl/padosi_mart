import { api } from "./client";

export type StoreOrderStatus =
  | "PLACED"
  | "SELLER_ACCEPTED"
  | "PREPARING"
  | "READY_FOR_PICKUP"
  | "PICKED_UP"
  | "CANCELLED"
  | "REJECTED";

export type RemovalReason = "OUT_OF_STOCK" | "QUALITY_ISSUE" | "SHOP_CLOSING" | "OTHER";

export type SellerOrderItem = {
  id: string;
  product_id: string;
  name: string;
  selling_unit: string;
  quantity: number;
  unit_price: number;
  line_total: number;
  removed: boolean;
  removed_reason_code: string | null;
  removed_reason: string | null;
  removed_kept_quantity: number | null;
};

export type SellerOrder = {
  id: string; // store_order id
  order_id: string;
  order_number: string;
  store_id: string;
  store_name: string;
  status: StoreOrderStatus;
  payment_method: "COD" | "ONLINE";
  items_subtotal: number;
  seller_discount: number;
  items: SellerOrderItem[];
  created_at: string;
  updated_at: string;
};

export const listSellerOrders = (status?: StoreOrderStatus, limit = 100, offset = 0) =>
  api<SellerOrder[]>("/seller/orders", { query: { status, limit, offset } });

export const getSellerOrder = (id: string) => api<SellerOrder>(`/seller/orders/${id}`);

const move = (id: string, step: "accept" | "preparing" | "ready") =>
  api<SellerOrder>(`/seller/orders/${id}/${step}`, { method: "POST" });

export const acceptOrder = (id: string) => move(id, "accept");
export const preparingOrder = (id: string) => move(id, "preparing");
export const readyOrder = (id: string) => move(id, "ready");

export const rejectOrder = (id: string, reason: string, reason_code: RemovalReason) =>
  api<SellerOrder>(`/seller/orders/${id}/reject`, { method: "POST", body: { reason, reason_code } });

export const markUnavailable = (
  id: string,
  items: { item_id: string; reason: RemovalReason; note?: string | null; available_quantity: number }[],
) => api<SellerOrder>(`/seller/orders/${id}/unavailable`, { method: "POST", body: { items } });
