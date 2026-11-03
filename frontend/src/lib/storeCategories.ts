export const STORE_CATEGORIES = [
  { value: "GROCERY", label: "Kirana / General store" },
  { value: "RESTAURANT", label: "Restaurant / Cafe" },
  { value: "HARDWARE", label: "Hardware" },
  { value: "MEDICAL", label: "Medical / Pharmacy" },
  { value: "CLOTHING", label: "Garments / Clothing" },
  { value: "MOBILE_ELECTRONICS", label: "Mobile / Electronics" },
  { value: "FOOTWEAR", label: "Shoes / Footwear" },
  { value: "FRUITS_VEGETABLES", label: "Fruits / Vegetables" },
  { value: "DAIRY", label: "Dairy" },
  { value: "BAKERY", label: "Bakery / Sweets" },
  { value: "STATIONERY", label: "Stationery" },
  { value: "BEAUTY_COSMETICS", label: "Beauty / Cosmetics" },
  { value: "HOME_FURNITURE", label: "Home / Furniture" },
  { value: "ELECTRICAL", label: "Electrical" },
  { value: "AUTO_PARTS", label: "Auto parts / Accessories" },
  { value: "PET_SUPPLIES", label: "Pet supplies" },
  { value: "BOOKS_GIFTS", label: "Books / Gifts" },
  { value: "SPORTS", label: "Sports / Fitness" },
  { value: "AGRICULTURE", label: "Agriculture / Seeds" },
  { value: "OTHER", label: "Other" },
] as const;

export type StoreCategoryCode = (typeof STORE_CATEGORIES)[number]["value"];
export const storeCategoryLabel = (code: string) => STORE_CATEGORIES.find((item) => item.value === code)?.label ?? "Other";
