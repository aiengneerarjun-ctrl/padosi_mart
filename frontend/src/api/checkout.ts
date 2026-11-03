import { api } from "./client";
import { Address } from "./address";
import { CartStoreGroup } from "./cart";

export type CouponBrief = { code: string; title: string; discount_type: string };

export type CheckoutPreview = {
  address: Address;
  stores: CartStoreGroup[];
  item_count: number;
  items_subtotal: number;
  delivery_fee: number;
  free_delivery_from: number;
  free_delivery_remaining: number; // 0 = free delivery mil rahi hai
  discount_amount: number;
  coupon: CouponBrief | null;
  coupon_error: string | null; // coupon_code bheja par chala nahi
  coupon_message: string | null; // wahi, customer ki bhasha me
  total: number;
  can_checkout: boolean;
  blockers: string[]; // CART_EMPTY / ITEM_UNAVAILABLE
};

export type CouponOut = {
  id: string;
  code: string;
  title: string;
  discount_type: string; // FLAT / PERCENT / FREE_DELIVERY
  value: number;
  max_discount: number | null;
  min_order_amount: number;
  first_order_only: boolean;
  seller_id: string | null;
  expires_at: string;
  usable: boolean;
  unusable_reason: string | null;
  unusable_message: string | null;
};

// address_id nahi bhejte: backend default address lagata hai
export const previewCheckout = (couponCode?: string | null) =>
  api<CheckoutPreview>("/checkout/preview", { query: { coupon_code: couponCode || undefined } });

export const listCoupons = () => api<CouponOut[]>("/coupons", { query: { limit: 20 } });
