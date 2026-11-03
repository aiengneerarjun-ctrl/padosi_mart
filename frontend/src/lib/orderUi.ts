// Backend ke order status ko customer ki bhasha me dikhane ke liye

const LABEL: Record<string, string> = {
  PLACED: "Order mil gaya",
  CONFIRMED: "Order pakka ho gaya",
  SELLER_ACCEPTED: "Dukaan ne order le liya",
  PREPARING: "Saman taiyaar ho raha hai",
  READY_FOR_PICKUP: "Saman taiyaar hai",
  DELIVERY_ASSIGNED: "Delivery partner mil gaya",
  PICKED_UP: "Saman uth gaya",
  OUT_FOR_DELIVERY: "Raaste me hai",
  DELIVERED: "Pahunch gaya",
  CANCELLED: "Cancel ho gaya",
  PAYMENT_FAILED: "Payment nahi ho payi",
  REFUND_PENDING: "Paisa wapas aa raha hai",
  REFUNDED: "Paisa wapas ho gaya",
  RETURN_REQUESTED: "Return maanga gaya",
  FAILED_DELIVERY: "Delivery nahi ho payi",
};

export const statusLabel = (s: string) => LABEL[s] ?? s;

export type Tone = "progress" | "good" | "bad";

export function statusTone(s: string): Tone {
  if (s === "DELIVERED" || s === "REFUNDED") return "good";
  if (s === "CANCELLED" || s === "PAYMENT_FAILED" || s === "FAILED_DELIVERY") return "bad";
  return "progress";
}

export const TONE_COLORS: Record<Tone, { bg: string; fg: string }> = {
  progress: { bg: "#FCE9C2", fg: "#C98A00" },
  good: { bg: "#DDF1E4", fg: "#1F8A4C" },
  bad: { bg: "#F7DAD7", fg: "#C8372D" },
};

// Jab tak order chal raha hai, app status baar-baar taza karti hai
export const isActiveOrder = (s: string) =>
  !["DELIVERED", "CANCELLED", "PAYMENT_FAILED", "REFUNDED", "FAILED_DELIVERY"].includes(s);

export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
}