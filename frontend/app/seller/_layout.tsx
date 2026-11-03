import { Stack } from "expo-router";
import { SellerProvider } from "../../src/seller/SellerContext";
import { colors } from "../../src/theme";

// Seller ke saare screens ek hi SellerProvider ke andar chalte hain
// (seller aur dukaan ki jaankari baar-baar nahi mangwani padti).
export default function SellerLayout() {
  return (
    <SellerProvider>
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.canvas } }} />
    </SellerProvider>
  );
}
