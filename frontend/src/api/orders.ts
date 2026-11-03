import { api } from "./client";

export type OrderItemOut = {
  product_id: string;
  name: string;
  selling_unit: string;
  mrp: number;
  unit_price: number;
  quantity: number;
  line_total: number;
  removed: boolean;
  removed_reason: string | null;
  removed_note: string | null;
  removed_kept_quantity: number | null;
};

export type RemovedItemOut = {
  product_id: string;
  name: string;
  selling_unit: string;
  quantity: number;
  line_total: number;
  store_name: string;
  reason: string;
  note: string | null;
  kept_quantity: number | null;
};

export type StoreOrderOut = {
  id: string;
  store_id: string;
  store_name: string;
  store_address: string;
  status: string;
  items_subtotal: number;
  items: OrderItemOut[];
};

export type StatusHistoryOut = {
  store_order_id: string | null;
  from_status: string | null;
  to_status: string;
  actor_role: string;
  note: string | null;
  created_at: string;
};

export type OrderOut = {
  id: string;
  order_number: string;
  status: string;
  payment_method: "COD" | "ONLINE";
  payment_status: string;
  address: {
    receiver_name: string;
    receiver_phone: string;
    address_line: string;
    landmark: string | null;
    latitude: number;
    longitude: number;
  };
  items_subtotal: number;
  delivery_fee: number;
  total: number;
  original_items_subtotal: number;
  original_total: number;
  removed_total: number;
  delivery_fee_added: number;
  coupon_code: string | null;
  discount_amount: number;
  discount_lost: number;
  can_cancel: boolean;
  seller_can_accept_after: string | null;
  amount_due: number;
  delivery_otp: string | null;
  refunded_total: number;
  payment_expires_at: string | null;
  removed_items: RemovedItemOut[];
  notice: string | null;
  note: string | null;
  created_at: string;
  stores: StoreOrderOut[];
  history: StatusHistoryOut[];
};

export type OrderSummary = {
  id: string;
  order_number: string;
  status: string;
  payment_method: string;
  payment_status: string;
  total: number;
  has_removed_items: boolean;
  store_names: string[];
  item_count: number;
  created_at: string;
};

export type PlaceOrderBody = {
  address_id?: string;
  payment_method: "COD" | "ONLINE";
  expected_total: number; // preview me jo total dikha tha wahi
  note?: string;
  coupon_code?: string;
};

// Har naye order ke liye nayi key. Retry me wahi key, to duplicate order nahi banta.
export const placeOrder = (body: PlaceOrderBody, idempotencyKey: string) =>
  api<OrderOut>("/orders", { method: "POST", body, headers: { "Idempotency-Key": idempotencyKey } });

export const listOrders = (limit = 20, offset = 0) => api<OrderSummary[]>("/orders", { query: { limit, offset } });

export const getOrder = (id: string) => api<OrderOut>(`/orders/${id}`);

export const cancelOrder = (id: string, reason?: string) =>
  api<OrderOut>(`/orders/${id}/cancel`, { method: "POST", body: reason ? { reason } : {} });
export type PaymentSession = {
  order_id: string;
  provider_order_id: string;
  payment_session_id: string;
  amount: number;
  environment: string; // "sandbox" ya "production"
  expires_at: string;
};

// Online order ka payment shuru karo. Dobara bulane par wahi session milta hai.
export const startPayment = (orderId: string) => api<PaymentSession>(`/orders/${orderId}/pay`, { method: "POST" });