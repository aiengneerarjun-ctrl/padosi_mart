import * as ImagePicker from "expo-image-picker";
import { PickedImage, ProductStatus } from "../api/sellerProducts";
import { BadgeTone } from "../components/seller/ui";

export const PRODUCT_STATUS: Record<ProductStatus, { label: string; tone: BadgeTone; hint: string }> = {
  PENDING_APPROVAL: {
    label: "Review me",
    tone: "progress",
    hint: "Admin dekh raha hai. Approve hone ke baad hi customer ko dikhega. Kam se kam ek photo zaroori hai.",
  },
  ACTIVE: { label: "Live", tone: "good", hint: "Customer ko dikh raha hai." },
  OUT_OF_STOCK: { label: "Stock khatam", tone: "bad", hint: "Stock 0 hai, isliye customer order nahi kar sakta. Stock badhate hi wapas dikhega." },
  INACTIVE: { label: "Chhupa hua", tone: "neutral", hint: "Aapne ise chhupaya hai. Customer ko nahi dikhta." },
  REJECTED: { label: "Reject hua", tone: "bad", hint: "Neeche wajah dekhkar sudhaar karein aur save karein, dobara review me chala jayega." },
};

// Phone ki gallery se photo chunna. Max kitni aur chun sakte hain wo `limit` se tay hota hai.
export async function pickImages(limit: number): Promise<PickedImage[]> {
  if (limit <= 0) return [];
  const res = await ImagePicker.launchImageLibraryAsync({
    mediaTypes: ["images"],
    allowsMultipleSelection: limit > 1,
    selectionLimit: limit,
    quality: 0.85,
  });
  if (res.canceled) return [];
  return res.assets.map((a) => ({ uri: a.uri, name: a.fileName, mimeType: a.mimeType }));
}

export function makeSku(): string {
  return `P${Date.now().toString(36).toUpperCase()}${Math.random().toString(36).slice(2, 5).toUpperCase()}`;
}
