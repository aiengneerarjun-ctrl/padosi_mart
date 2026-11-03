import { ActivityIndicator, Alert, Pressable, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useCart } from "../cart/CartContext";
import { colors, radius, type } from "../theme";

const MAX_QTY = 20; // backend: ek product ki zyada se zyada quantity

// Apne parent ki poori chaudai leta hai. Chaudai parent tay karta hai.
export function QtyControl({ productId, large }: { productId: string; large?: boolean }) {
  const { qtyOf, setQty, isBusy } = useCart();
  const qty = qtyOf(productId);
  const busy = isBusy(productId);
  const h = large ? 48 : 34;

  const change = async (next: number) => {
    const err = await setQty(productId, next);
    if (err) Alert.alert("Cart", err);
  };

  if (qty === 0) {
    return (
      <Pressable
        onPress={() => change(1)}
        disabled={busy}
        style={({ pressed }) => ({
          height: h,
          width: "100%",
          borderRadius: radius.pill,
          backgroundColor: large ? colors.marigold : colors.surface,
          borderWidth: large ? 0 : 1.5,
          borderColor: colors.ink,
          alignItems: "center",
          justifyContent: "center",
          opacity: busy ? 0.5 : pressed ? 0.85 : 1,
        })}
      >
        {busy ? (
          <ActivityIndicator size="small" color={large ? colors.onMarigold : colors.ink} />
        ) : (
          <Text style={{ ...type.heading, color: large ? colors.onMarigold : colors.ink }}>
            {large ? "Cart me daalein" : "Add"}
          </Text>
        )}
      </Pressable>
    );
  }

  const btn = { width: large ? 52 : 38, height: h, alignItems: "center" as const, justifyContent: "center" as const };

  return (
    <View
      style={{
        height: h,
        width: "100%",
        borderRadius: radius.pill,
        backgroundColor: colors.ink,
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "space-between",
      }}
    >
      <Pressable onPress={() => change(qty - 1)} disabled={busy} hitSlop={6} style={btn}>
        <Ionicons name="remove" size={large ? 22 : 18} color={colors.onInk} />
      </Pressable>
      {busy ? (
        <ActivityIndicator size="small" color={colors.onInk} />
      ) : (
        <Text style={{ ...type.heading, color: colors.onInk }}>{qty}</Text>
      )}
      <Pressable
        onPress={() => change(qty + 1)}
        disabled={busy || qty >= MAX_QTY}
        hitSlop={6}
        style={[btn, { opacity: qty >= MAX_QTY ? 0.4 : 1 }]}
      >
        <Ionicons name="add" size={large ? 22 : 18} color={colors.onInk} />
      </Pressable>
    </View>
  );
}