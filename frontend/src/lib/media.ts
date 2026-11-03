import { API_BASE_URL } from "../config";

// Backend photo ka URL apne config ke hisaab se bhejta hai, jaise:
//   http://localhost:8000/media/...        (local storage, backend khud dikhata hai)
//   http://localhost:9000/padosi-media/... (MinIO / S3 storage, alag port par)
// Phone par "localhost" apna hi phone hota hai, isliye use computer ke address se badalna padta hai.
export function fixMediaUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  // Local storage: backend ke apne server se
  const local = url.match(/^https?:\/\/[^/]+(\/media\/.*)$/);
  if (local) return API_BASE_URL + local[1];
  // MinIO / S3: port wahi rakho (jaise 9000), sirf localhost ki jagah computer ka IP lagao
  const api = API_BASE_URL.match(/^(https?):\/\/([^/:]+)/);
  // Backend kabhi MinIO ka Docker-only hostname (jaise `minio`) bhejta hai.
  // Phone us hostname ko resolve nahi kar sakta; API ke reachable host par port/path rakhein.
  if (api) {
    return url.replace(
      /^(https?):\/\/(localhost|127\.0\.0\.1|0\.0\.0\.0|minio|storage)(?=[:/]|$)/i,
      `${api[1]}://${api[2]}`,
    );
  }
  return url;
}

export function formatPrice(n: number): string {
  return "₹" + (Number.isInteger(n) ? String(n) : n.toFixed(2));
}
