import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { ActivityIndicator, View } from "react-native";
import {
  useFonts,
  Hind_400Regular,
  Hind_500Medium,
  Hind_600SemiBold,
  Hind_700Bold,
} from "@expo-google-fonts/hind";
import { AuthProvider, useAuth } from "../src/auth/AuthContext";
import { CartProvider } from "../src/cart/CartContext";
import { FavouritesProvider } from "../src/favourites/FavouritesContext";
import { LocationProvider } from "../src/lib/LocationContext";
import { colors } from "../src/theme";

function Loading() {
  return (
    <View style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.canvas }}>
      <ActivityIndicator color={colors.ink} />
    </View>
  );
}

// Login hai to customer ya seller ke screens, nahi hai to sirf login screens
function Gate() {
  const { status, mode } = useAuth();
  if (status === "loading") return <Loading />;
  const signedIn = status === "signedIn";
  const customer = signedIn && mode === "customer";
  const seller = signedIn && mode === "seller";
  const delivery = signedIn && mode === "delivery";

  return (
    <LocationProvider enabled={customer}>
      <FavouritesProvider>
        <CartProvider>
          <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.canvas } }}>
            <Stack.Protected guard={customer}>
              <Stack.Screen name="index" />
              <Stack.Screen name="store/[id]" />
              <Stack.Screen name="product/[id]" />
              <Stack.Screen name="cart" />
              <Stack.Screen name="checkout" />
              <Stack.Screen name="addresses" />
              <Stack.Screen name="address-new" />
              <Stack.Screen name="order/[id]" />
              <Stack.Screen name="orders" />
              <Stack.Screen name="pay/[id]" />
            </Stack.Protected>
            <Stack.Protected guard={seller}>
              <Stack.Screen name="seller" />
            </Stack.Protected>
            <Stack.Protected guard={delivery}>
              <Stack.Screen name="delivery/index" />
              <Stack.Screen name="delivery/apply" />
            </Stack.Protected>
            <Stack.Protected guard={!signedIn}>
              <Stack.Screen name="login" />
              <Stack.Screen name="otp" />
            </Stack.Protected>
          </Stack>
        </CartProvider>
      </FavouritesProvider>
    </LocationProvider>
  );
}

export default function RootLayout() {
  const [loaded] = useFonts({ Hind_400Regular, Hind_500Medium, Hind_600SemiBold, Hind_700Bold });
  if (!loaded) return <Loading />;

  return (
    <AuthProvider>
      <StatusBar style="light" />
      <Gate />
    </AuthProvider>
  );
}
