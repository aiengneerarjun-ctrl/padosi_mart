import { api } from "./client";

// ---------------- Kamai ----------------

export type SettlementOrder = {
  order_id: string;
  order_number: string;
  store_name: string;
  items_subtotal: number;
  commission_rate: number;
  commission_amount: number;
  seller_discount: number;
  net: number;
  delivered_at: string;
  commission_items: { name: string; selling_unit: string; quantity: number; commission_mode: string; commission_unit: string; commission_value: number; commission_unit_quantity: number; commission_amount: number }[];
};

export type SellerPayout = { id: string; amount: number; note: string | null; created_at: string };

export type EarningsSummary = {
  total_sales: number;
  total_commission: number;
  total_seller_discount: number;
  total_earned: number;
  total_paid: number;
  due: number;
  recent_orders: SettlementOrder[];
  recent_payouts: SellerPayout[];
};

export const getEarnings = () => api<EarningsSummary>("/seller/earnings");

// ---------------- Coupons ----------------

export type SellerCoupon = {
  id: string;
  code: string;
  title: string;
  discount_type: "FLAT" | "PERCENT" | "FREE_DELIVERY";
  value: number;
  max_discount: number | null;
  min_order_amount: number;
  first_order_only: boolean;
  is_public: boolean;
  per_user_limit: number;
  total_limit: number | null;
  starts_at: string;
  expires_at: string;
  is_active: boolean;
  used_count: number;
  total_discount_given: number;
  created_at: string;
};

export type CouponCreateBody = {
  code: string;
  title: string;
  discount_type: "FLAT" | "PERCENT";
  value: string;
  max_discount?: string | null;
  min_order_amount: string;
  first_order_only: boolean;
  is_public: boolean;
  per_user_limit: number;
  total_limit?: number | null;
  expires_at: string; // ISO, timezone ke saath
};

export const listCoupons = (limit = 50, offset = 0) => api<SellerCoupon[]>("/seller/coupons", { query: { limit, offset } });
export const createCoupon = (body: CouponCreateBody) => api<SellerCoupon>("/seller/coupons", { method: "POST", body });
export const setCouponActive = (id: string, is_active: boolean) =>
  api<SellerCoupon>(`/seller/coupons/${id}`, {
    method: "PATCH",
    body: { is_active, reason: is_active ? "Seller ne coupon chalu kiya" : "Seller ne coupon band kiya" },
  });

// ---------------- Returns ----------------

export type ReturnOut = {
  store_order_id: string;
  order_id: string;
  order_number: string;
  store_id: string;
  store_name: string;
  status: "PENDING" | "RECEIVED";
  was_picked_up: boolean;
  fail_reason: string | null;
  items: { name: string; quantity: number; selling_unit: string }[];
  restocked: boolean;
  received_at: string | null;
  received_role: string | null;
  note: string | null;
  created_at: string;
};

export const listReturns = (status?: "PENDING" | "RECEIVED") =>
  api<ReturnOut[]>("/seller/returns", { query: { status, limit: 50 } });
export const receiveReturn = (storeOrderId: string, stock_ok: boolean, note?: string) =>
  api<ReturnOut>(`/seller/returns/${storeOrderId}/received`, { method: "POST", body: { stock_ok, note: note || null } });

// ---------------- Reviews ----------------

export type RatingSummary = { average: number | null; count: number; stars: Record<string, number> };

export type SellerReview = {
  id: string;
  store_id: string;
  store_name: string;
  order_number: string;
  rating: number;
  comment: string | null;
  reviewer_name: string;
  created_at: string;
};

export type SellerReviews = { summary: RatingSummary; reviews: SellerReview[] };

export const getSellerReviews = (maxRating?: number) =>
  api<SellerReviews>("/seller/reviews", { query: { max_rating: maxRating, limit: 50 } });
