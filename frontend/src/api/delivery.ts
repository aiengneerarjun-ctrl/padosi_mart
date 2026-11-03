import { File } from "expo-file-system";
import { api } from "./client";

export type VehicleType = "BICYCLE" | "BIKE" | "SCOOTER";
export type IdType = "AADHAAR" | "PAN";

export type DeliveryPartner = {
  id: string;
  full_name: string;
  phone: string;
  vehicle_type: VehicleType;
  vehicle_number: string | null;
  id_type: IdType;
  has_licence_photo: boolean;
  status: "PENDING" | "ACTIVE" | "REJECTED" | "SUSPENDED";
  status_reason: string | null;
  is_online: boolean;
  created_at: string;
};

export type PickupItem = { name: string; quantity: number; selling_unit: string };
export type PickupStore = {
  store_order_id: string;
  store_name: string;
  store_address: string;
  latitude: number;
  longitude: number;
  status: string;
  items: PickupItem[];
};

export type AvailableDelivery = {
  order_id: string;
  order_number: string;
  stores: PickupStore[];
  pickup_distance_km: number | null;
  drop_distance_km: number;
  delivery_fee: number;
  payment_method: string;
  amount_due: number;
  created_at: string;
};

export type MyDelivery = {
  delivery_id: string;
  order_id: string;
  order_number: string;
  status: "ASSIGNED" | "PICKED_UP" | "OUT_FOR_DELIVERY";
  order_status: string;
  assigned_at: string;
  stores: PickupStore[];
  receiver_name: string;
  receiver_phone: string;
  address_line: string;
  landmark: string | null;
  latitude: number;
  longitude: number;
  delivery_fee: number;
  payment_method: string;
  amount_due: number;
};

export type DeliveryEarnings = {
  total_earned: number;
  total_paid: number;
  due: number;
  recent_earnings: { order_id: string; order_number: string; amount: number; delivered_at: string }[];
  recent_payouts: { id: string; amount: number; note: string | null; created_at: string }[];
};

export type DeliveryCash = {
  cash_collected: number;
  cash_deposited: number;
  cash_in_hand: number;
  cash_limit: number;
  limit_reached: boolean;
  recent_collections: { order_id: string; order_number: string; amount: number; delivered_at: string }[];
  recent_deposits: { id: string; amount: number; note: string | null; created_at: string }[];
};

export type DeliveryReviews = {
  summary: { average: number | null; count: number; stars: Record<number, number> };
  reviews: { rating: number; comment: string | null; order_number: string; created_at: string }[];
};

export type PickedPhoto = { uri: string; name?: string | null; mimeType?: string | null };

export const getDeliveryPartner = () => api<DeliveryPartner>("/delivery/me");
export const goOnline = () => api<DeliveryPartner>("/delivery/me/online", { method: "POST" });
export const goOffline = () => api<DeliveryPartner>("/delivery/me/offline", { method: "POST" });
export const getAvailableDeliveries = (lat: number, lng: number) =>
  api<AvailableDelivery[]>("/delivery/orders/available", { query: { lat, lng, limit: 50 } });
export const getCurrentDelivery = () => api<MyDelivery[]>("/delivery/orders/current");
export const acceptDelivery = (orderId: string, lat: number, lng: number) =>
  api<MyDelivery>(`/delivery/orders/${orderId}/accept`, { method: "POST", query: { lat, lng } });
export const releaseDelivery = (orderId: string) =>
  api<{ order_id: string; released: boolean }>(`/delivery/orders/${orderId}/release`, { method: "POST" });
export const pickupStoreOrder = (orderId: string, storeOrderId: string) =>
  api<MyDelivery>(`/delivery/orders/${orderId}/stores/${storeOrderId}/pickup`, { method: "POST" });
export const startDelivery = (orderId: string) =>
  api<MyDelivery>(`/delivery/orders/${orderId}/start`, { method: "POST" });
export const confirmDelivery = (orderId: string, otp: string) =>
  api<{ order_id: string; order_number: string; status: string; cod_collected: number; delivered_at: string }>(
    `/delivery/orders/${orderId}/deliver`, { method: "POST", body: { otp } },
  );
export const failDelivery = (orderId: string, reason_code: string, note?: string) =>
  api<{ order_id: string; order_number: string; status: string }>(`/delivery/orders/${orderId}/fail`, {
    method: "POST", body: { reason_code, note: note || null },
  });
export const getDeliveryCash = () => api<DeliveryCash>("/delivery/me/cash");
export const getDeliveryEarnings = () => api<DeliveryEarnings>("/delivery/me/earnings");
export const getDeliveryReviews = () => api<DeliveryReviews>("/delivery/reviews");

export function applyAsDeliveryPartner(input: {
  full_name: string;
  vehicle_type: VehicleType;
  vehicle_number: string;
  id_type: IdType;
  id_photo: PickedPhoto;
  licence_photo?: PickedPhoto | null;
}) {
  const form = new FormData();
  form.append("full_name", input.full_name);
  form.append("vehicle_type", input.vehicle_type);
  form.append("vehicle_number", input.vehicle_number);
  form.append("id_type", input.id_type);
  form.append("id_photo", new File(input.id_photo.uri) as unknown as Blob);
  if (input.licence_photo) form.append("licence_photo", new File(input.licence_photo.uri) as unknown as Blob);
  return api<DeliveryPartner>("/delivery/apply", { method: "POST", body: form, timeoutMs: 60000 });
}
