import Constants from "expo-constants";
import { Platform } from "react-native";

// Expo ka dev server jis IP par chal raha hai, backend bhi usi computer par hai.
// Isliye wahi IP use karte hain (phone is IP tak pehle se pahunch raha hota hai).
function guessDevUrl(): string {
  const hostUri = Constants.expoConfig?.hostUri; // jaise "10.76.109.20:8081"
  if (hostUri) {
    const host = hostUri.split(":")[0];
    return `http://${host}:8000`;
  }
  // Android emulator me computer ka address 10.0.2.2 hota hai
  return Platform.OS === "android" ? "http://10.0.2.2:8000" : "http://localhost:8000";
}

export const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL || guessDevUrl();
export const API_PREFIX = "/api/v1";
// Location permission na mile ya GPS band ho to ye use hogi.
// Barharia (district Siwan, Bihar). Bahadurpur aur Bishambharpur isi ke aas-paas hain.
export const DEFAULT_LOCATION = { lat: 26.319, lng: 84.459 };