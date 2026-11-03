import { Pressable, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useCart } from "../cart/CartContext";
import { formatPrice } from "../lib/media";
import { colors, radius, shadow, space, type } from "../theme";

// Cart me kuch ho to screen ke neeche dikhta hai
export function FloatingCartBar() {
  const { cart } = useCart();
  const router = useRouter();
  const insets = useSafeAreaInsets();

  if (!cart || cart.item_count === 0) return null;

  return (
    <Pressable
      onPress={() => router.push("/cart")}
      style={{
        position: "absolute",
        left: space.lg,
        right: space.lg,
        bottom: insets.bottom + space.md,
        backgroundColor: colors.ink,
        borderRadius: radius.pill,
        paddingVertical: space.md,
        paddingHorizontal: space.xl,
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "space-between",
        ...shadow.raised,
      }}
    >
      <View>
        <Text style={{ ...type.caption, color: "#B9D3CF" }}>{cart.item_count} item</Text>
        <Text style={{ ...type.heading, color: colors.onInk }}>{formatPrice(cart.subtotal)}</Text>
      </View>
      <View style={{ flexDirection: "row", alignItems: "center" }}>
        <Text style={{ ...type.heading, color: colors.marigold }}>Cart dekhein</Text>
        <Ionicons name="chevron-forward" size={18} color={colors.marigold} />
      </View>
    </Pressable>
  );
}