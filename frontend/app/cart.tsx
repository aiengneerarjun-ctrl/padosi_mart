import { useCallback } from "react";
import { ActivityIndicator, Alert, Image, Pressable, ScrollView, Text, View } from "react-native";
import { useFocusEffect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { CartItemOut } from "../src/api/cart";
import { useCart } from "../src/cart/CartContext";
import { IconButton } from "../src/components/IconButton";
import { QtyControl } from "../src/components/QtyControl";
import { fixMediaUrl, formatPrice } from "../src/lib/media";
import { storeCategoryLabel } from "../src/lib/storeCategories";
import { colors, radius, space, type } from "../src/theme";

function reasonText(item: CartItemOut): string {
  switch (item.unavailable_reason) {
    case "PRODUCT_INACTIVE":
      return "Ye product abhi nahi mil raha.";
    case "STORE_CLOSED":
      return "Dukaan abhi band hai.";
    case "SELLER_INACTIVE":
      return "Ye dukaan abhi available nahi hai.";
    case "NOT_DELIVERABLE":
      return "Ye dukaan aapke area me deliver nahi karti.";
    case "OUT_OF_STOCK":
      return "Stock khatam ho gaya.";
    case "LOW_STOCK":
      return `Itna stock nahi hai. Sirf ${item.stock_left} bache hain.`;
    default:
      return "Ye item abhi available nahi hai.";
  }
}

function Row({ item }: { item: CartItemOut }) {
  const { setQty } = useCart();
  const img = fixMediaUrl(item.image_thumb_url);
  const lowStock = item.unavailable_reason === "LOW_STOCK";
  const dead = !item.available && !lowStock; // quantity kam karne se bhi theek nahi hoga: hatana padega

  const remove = async () => {
    const err = await setQty(item.product_id, 0);
    if (err) Alert.alert("Cart", err);
  };

  return (
    <View style={{ flexDirection: "row", paddingVertical: space.md }}>
      <View
        style={{
          width: 64,
          height: 64,
          borderRadius: radius.sm,
          backgroundColor: "#EDF2F1",
          overflow: "hidden",
          opacity: dead ? 0.5 : 1,
        }}
      >
        {img && <Image source={{ uri: img }} style={{ width: "100%", height: "100%" }} resizeMode="cover" />}
      </View>

      <View style={{ flex: 1, marginLeft: space.md }}>
        <Text numberOfLines={2} style={{ ...type.body, color: dead ? colors.textMuted : colors.text }}>
          {item.name}
        </Text>
        <Text style={{ ...type.caption, color: colors.textMuted }}>
          {item.selling_unit} · {formatPrice(item.selling_price)}
        </Text>

        {!item.available && (
          <Text style={{ ...type.caption, color: colors.danger, marginTop: 2 }}>{reasonText(item)}</Text>
        )}

        <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: space.sm }}>
          {dead ? (
            <Pressable onPress={remove} hitSlop={8}>
              <Text style={{ ...type.body, color: colors.danger }}>Hatayein</Text>
            </Pressable>
          ) : (
            <View style={{ width: 110 }}>
              <QtyControl productId={item.product_id} />
            </View>
          )}
          <Text style={{ ...type.heading, color: dead ? colors.textMuted : colors.text }}>
            {formatPrice(item.line_total)}
          </Text>
        </View>
      </View>
    </View>
  );
}

export default function CartScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { cart, loading, refresh, clear } = useCart();

  // Cart khulte hi taza karo (stock ya dukaan ki status badal gayi ho sakti hai)
  useFocusEffect(
    useCallback(() => {
      refresh();
    }, [refresh]),
  );

  const confirmClear = () =>
    Alert.alert("Cart khali karein?", "Saare items hat jayenge.", [
      { text: "Nahi", style: "cancel" },
      {
        text: "Haan, khali karein",
        style: "destructive",
        onPress: async () => {
          const err = await clear();
          if (err) Alert.alert("Cart", err);
        },
      },
    ]);

  const empty = !cart || cart.stores.length === 0;

  return (
    <View style={{ flex: 1, backgroundColor: colors.canvas }}>
      <View
        style={{
          flexDirection: "row",
          alignItems: "center",
          backgroundColor: colors.ink,
          paddingTop: insets.top + space.sm,
          paddingHorizontal: space.lg,
          paddingBottom: space.md,
        }}
      >
        <IconButton name="arrow-back" onPress={() => (router.canGoBack() ? router.back() : router.replace("/"))} />
        <Text style={{ ...type.title, color: colors.onInk, flex: 1, marginLeft: space.md }}>Aapka cart</Text>
        {!empty && (
          <Pressable onPress={confirmClear} hitSlop={10}>
            <Text style={{ ...type.body, color: colors.marigold }}>Khali karein</Text>
          </Pressable>
        )}
      </View>

      {loading && !cart ? (
        <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
          <ActivityIndicator color={colors.ink} />
        </View>
      ) : empty ? (
        <View style={{ flex: 1, alignItems: "center", justifyContent: "center", padding: space.xl }}>
          <Text style={{ ...type.title, color: colors.text }}>Cart khali hai</Text>
          <Text style={{ ...type.body, color: colors.textMuted, marginTop: space.xs, textAlign: "center" }}>
            Paas ki dukaanein dekhein aur kuch pasand ka saman jodein.
          </Text>
          <Pressable
            onPress={() => (router.canGoBack() ? router.back() : router.replace("/"))}
            style={{
              marginTop: space.xl,
              backgroundColor: colors.marigold,
              paddingVertical: 14,
              paddingHorizontal: space.xl,
              borderRadius: radius.pill,
            }}
          >
            <Text style={{ ...type.heading, color: colors.onMarigold }}>Dukaanein dekhein</Text>
          </Pressable>
        </View>
      ) : (
        <>
          <ScrollView
            contentContainerStyle={{ padding: space.lg, paddingBottom: insets.bottom + 200 }}
            showsVerticalScrollIndicator={false}
          >
            {cart!.stores.length > 1 && (
              <Text style={{ ...type.caption, color: colors.textMuted, marginBottom: space.md }}>
                Aapke cart me {cart!.stores.length} dukaanon ka saman hai.
              </Text>
            )}

            {cart!.stores.map((g) => (
              <View
                key={g.store_id}
                style={{
                  backgroundColor: colors.surface,
                  borderRadius: radius.md,
                  borderWidth: 1,
                  borderColor: colors.line,
                  padding: space.lg,
                  marginBottom: space.lg,
                }}
              >
                <Text style={{ ...type.heading, color: colors.text }}>{g.store_name}</Text>
                <Text style={{ ...type.caption, color: colors.textMuted }}>
                  {storeCategoryLabel(g.store_category)} · {g.distance_km.toFixed(1)} km
                </Text>

                <View style={{ marginTop: space.sm }}>
                  {g.items.map((item, i) => (
                    <View
                      key={item.product_id}
                      style={i > 0 ? { borderTopWidth: 1, borderTopColor: colors.line } : undefined}
                    >
                      <Row item={item} />
                    </View>
                  ))}
                </View>

                <View
                  style={{
                    flexDirection: "row",
                    justifyContent: "space-between",
                    borderTopWidth: 1,
                    borderTopColor: colors.line,
                    paddingTop: space.md,
                  }}
                >
                  <Text style={{ ...type.body, color: colors.textMuted }}>Is dukaan ka total</Text>
                  <Text style={{ ...type.heading, color: colors.text }}>{formatPrice(g.subtotal)}</Text>
                </View>
              </View>
            ))}
          </ScrollView>

          {/* Neeche ka total */}
          <View
            style={{
              position: "absolute",
              left: 0,
              right: 0,
              bottom: 0,
              backgroundColor: colors.surface,
              borderTopWidth: 1,
              borderTopColor: colors.line,
              padding: space.lg,
              paddingBottom: insets.bottom + space.md,
            }}
          >
            {cart!.has_problems && (
              <Text style={{ ...type.caption, color: colors.danger, marginBottom: space.sm }}>
                Kuch items available nahi hain. Unhe hatayein ya quantity kam karein.
              </Text>
            )}
            <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "baseline" }}>
              <Text style={{ ...type.body, color: colors.textMuted }}>Saman ka total ({cart!.item_count} item)</Text>
              <Text style={{ ...type.title, color: colors.text }}>{formatPrice(cart!.subtotal)}</Text>
            </View>
            <Text style={{ ...type.caption, color: colors.textMuted, marginTop: 2 }}>
              Delivery charge aur coupon checkout par judenge.
            </Text>
                        <Pressable
              onPress={() => router.push("/checkout")}
              disabled={cart!.has_problems}
              style={{
                marginTop: space.md,
                height: 48,
                borderRadius: radius.pill,
                backgroundColor: colors.marigold,
                alignItems: "center",
                justifyContent: "center",
                opacity: cart!.has_problems ? 0.45 : 1,
              }}
            >
              <Text style={{ ...type.heading, color: colors.onMarigold }}>Checkout par jaayein</Text>
            </Pressable>
          </View>
        </>
      )}
    </View>
  );
}
