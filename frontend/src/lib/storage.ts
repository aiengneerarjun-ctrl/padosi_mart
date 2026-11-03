import * as SecureStore from "expo-secure-store";

const ACCESS = "padosi.access";
const REFRESH = "padosi.refresh";
const LANG = "padosi.lang";

export type Tokens = { access_token: string; refresh_token: string };

export async function saveTokens(t: Tokens) {
  await SecureStore.setItemAsync(ACCESS, t.access_token);
  await SecureStore.setItemAsync(REFRESH, t.refresh_token);
}

export async function loadTokens(): Promise<Tokens | null> {
  const [access_token, refresh_token] = await Promise.all([
    SecureStore.getItemAsync(ACCESS),
    SecureStore.getItemAsync(REFRESH),
  ]);
  return access_token && refresh_token ? { access_token, refresh_token } : null;
}

export async function clearTokens() {
  await SecureStore.deleteItemAsync(ACCESS);
  await SecureStore.deleteItemAsync(REFRESH);
}

export type Lang = "en" | "hi" | "bho";

export async function saveLang(l: Lang) {
  await SecureStore.setItemAsync(LANG, l);
}
export async function loadLang(): Promise<Lang> {
  const v = await SecureStore.getItemAsync(LANG);
  return v === "hi" || v === "bho" || v === "en" ? v : "en";
}
export async function hasSavedLang(): Promise<boolean> {
  return (await SecureStore.getItemAsync(LANG)) !== null;
}
const MODE = "padosi.mode";
export type Mode = "customer" | "seller" | "delivery";

export async function saveMode(m: Mode) {
  await SecureStore.setItemAsync(MODE, m);
}
export async function loadMode(): Promise<Mode> {
  const v = await SecureStore.getItemAsync(MODE);
  return v === "seller" || v === "delivery" ? v : "customer";
}
