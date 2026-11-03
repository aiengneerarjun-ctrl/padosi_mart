import { api } from "./client";

export type AddressLabel = "HOME" | "WORK" | "OTHER";

export type Address = {
  id: string;
  label: string;
  receiver_name: string;
  receiver_phone: string;
  address_line: string;
  landmark: string | null;
  latitude: number;
  longitude: number;
  is_default: boolean;
};

export type AddressInput = {
  label: AddressLabel;
  receiver_name: string;
  receiver_phone: string;
  address_line: string;
  landmark?: string;
  latitude: number; // 6 decimal tak
  longitude: number;
  make_default: boolean;
};

export const listAddresses = () => api<Address[]>("/users/me/addresses");

export const createAddress = (body: AddressInput) =>
  api<Address>("/users/me/addresses", { method: "POST", body });

export const makeDefaultAddress = (id: string) =>
  api<Address>(`/users/me/addresses/${id}/default`, { method: "POST" });

export const deleteAddress = (id: string) =>
  api<void>(`/users/me/addresses/${id}`, { method: "DELETE" });