import { RemovalReason, StoreOrderStatus } from "../api/sellerOrders";
import { BadgeTone } from "../components/seller/ui";

export const STORE_ORDER_STATUS: Record<StoreOrderStatus, { label: string; tone: BadgeTone }> = {
  PLACED: { label: "Naya order", tone: "progress" },
  SELLER_ACCEPTED: { label: "Aapne le liya", tone: "progress" },
  PREPARING: { label: "Taiyaar ho raha hai", tone: "progress" },
  READY_FOR_PICKUP: { label: "Ready, partner ka intezaar", tone: "good" },
  PICKED_UP: { label: "Partner le gaya", tone: "good" },
  CANCELLED: { label: "Cancel hua", tone: "bad" },
  REJECTED: { label: "Aapne mana kiya", tone: "bad" },
};

export type OrderGroup = "new" | "active" | "ready" | "past";

export const GROUP_OF: Record<StoreOrderStatus, OrderGroup> = {
  PLACED: "new",
  SELLER_ACCEPTED: "active",
  PREPARING: "active",
  READY_FOR_PICKUP: "ready",
  PICKED_UP: "past",
  CANCELLED: "past",
  REJECTED: "past",
};

export const REMOVAL_REASONS: { value: RemovalReason; label: string }[] = [
  { value: "OUT_OF_STOCK", label: "Saman nahi hai" },
  { value: "QUALITY_ISSUE", label: "Quality theek nahi" },
  { value: "SHOP_CLOSING", label: "Dukaan band ho rahi hai" },
  { value: "OTHER", label: "Aur wajah" },
];

export const paymentLabel = (m: string) => (m === "COD" ? "Cash on delivery" : "Online paid");
