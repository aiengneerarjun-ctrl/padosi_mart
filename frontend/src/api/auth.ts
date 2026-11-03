import { api } from "./client";
import { Lang, loadTokens, Tokens } from "../lib/storage";

export type User = {
  id: string;
  phone: string;
  name: string | null;
  email: string | null;
  language: "en" | "hi" | "bho";
  roles: string[];
};

export const requestOtp = (phone: string) =>
  api<{ message: string }>("/auth/otp/request", { method: "POST", body: { phone }, auth: false });

export const verifyOtp = (phone: string, otp: string) =>
  api<Tokens>("/auth/otp/verify", { method: "POST", body: { phone, otp }, auth: false });

export const fetchMe = () => api<User>("/users/me");

export const updateLanguage = (language: Lang) =>
  api<User>("/users/me", { method: "PATCH", body: { language } });

export async function logoutRequest() {
  const t = await loadTokens();
  if (!t) return;
  try {
    await api("/auth/logout", { method: "POST", body: { refresh_token: t.refresh_token }, auth: false });
  } catch {
    // logout fail ho to bhi phone se session hata denge
  }
}
