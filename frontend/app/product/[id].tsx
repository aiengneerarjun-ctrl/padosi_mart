import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Image,
  NativeScrollEvent,
  NativeSyntheticEvent,
  Pressable,
  ScrollView,
  Text,
  useWindowDimensions,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useCart } from "../../src/cart/CartContext";
import { QtyControl } from "../../src/components/QtyControl";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { errorMessage } from "../../src/api/client";
import { fetchProduct, ProductDetail } from "../../src/api/shop";
import { IconButton } from "../../src/components/IconButton";
import { useFavourites } from "../../src/favourites/FavouritesContext";
import { useCoords } from "../../src/lib/LocationContext";
import { fixMediaUrl, formatPrice } from "../../src/lib/media";
import { colors, radius, space, type } from "../../src/theme";

export default function ProductScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { width } = useWindowDimensions();
  const coords = useCoords();
  const fav = useFavourites();
  const { qtyOf, cart } = useCart();

  const [p, setP] = useState<ProductDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [slide, setSlide] = useState(0);

  const lat = coords?.lat;
  const lng = coords?.lng;

  const load = useCallback(async () => {
    if (lat == null || lng == null || !id) return;
    setLoading(true);
    setError("");
    try {
      setP(await fetchProduct(id, { lat, lng }));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [id, lat, lng]);

  useEffect(() => {
    load();
  }, [load]);

  const topButtons = (
    <View
      style={{
        position: "absolute",
        top: insets.top + space.sm,
        left: space.lg,
        right: space.lg,
        flexDirection: "row",
        justifyContent: "space-between",
        zIndex: 5,
      }}
    >
      <IconButton name="arrow-back" onPress={() => (router.canGoBack() ? router.back() : router.replace("/"))} />
      {p && (
        <IconButton
          name={fav.isProductFav(p.id) ? "heart" : "heart-outline"}
          color={fav.isProductFav(p.id) ? colors.danger : colors.text}
          onPress={() => fav.toggleProduct(p.id)}
        />
      )}
    </View>
  );

  if (loading || !coords) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.canvas, alignItems: "center", justifyContent: "center" }}>
        {topButtons}
        <ActivityIndicator color={colors.ink} />
      </View>
    );
  }

  if (error || !p) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.canvas, alignItems: "center", justifyContent: "center", padding: space.xl }}>
        {topButtons}
        <Text style={{ ...type.body, color: colors.danger, textAlign: "center" }}>{error || "Product nahi mila."}</Text>
        <Pressable onPress={load} style={{ marginTop: space.lg }}>
          <Text style={{ ...type.heading, color: colors.ink }}>Dobara try karein</Text>
        </Pressable>
      </View>
    );
  }

  const urls = [...p.images]
    .sort((a, b) => a.position - b.position)
    .map((i) => fixMediaUrl(i.large_url))
    .filter((u): u is string => !!u);
  if (urls.length === 0) {
    const fallback = fixMediaUrl(p.image_medium_url || p.image_thumb_url);
    if (fallback) urls.push(fallback);
  }

  const hasDiscount = p.discount_percent > 0 && p.mrp > p.selling_price;
  const isFood = p.store.store_type === "RESTAURANT";

  const onScrollEnd = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    setSlide(Math.round(e.nativeEvent.contentOffset.x / width));
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.canvas }}>
      {topButtons}
      <ScrollView contentContainerStyle={{ paddingBottom: insets.bottom + 100 }}>
        {/* Photo swipe */}
        <View style={{ width, height: width, backgroundColor: "#EDF2F1" }}>
          {urls.length > 0 ? (
            <FlatList
              data={urls}
              keyExtractor={(u) => u}
              horizontal
              pagingEnabled
              showsHorizontalScrollIndicator={false}
              onMomentumScrollEnd={onScrollEnd}
              renderItem={({ item }) => (
                <Image source={{ uri: item }} style={{ width, height: width }} resizeMode="contain" />
              )}
            />
          ) : (
            <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
              <Text style={{ ...type.display, color: colors.textMuted }}>{p.name.slice(0, 1).toUpperCase()}</Text>
            </View>
          )}
          {urls.length > 1 && (
            <View style={{ position: "absolute", bottom: space.md, left: 0, right: 0, flexDirection: "row", justifyContent: "center" }}>
              {urls.map((u, i) => (
                <View
                  key={u}
                  style={{
                    width: i === slide ? 18 : 7,
                    height: 7,
                    borderRadius: 4,
                    marginHorizontal: 3,
                    backgroundColor: i === slide ? colors.ink : colors.line,
                  }}
                />
              ))}
            </View>
          )}
        </View>

        <View style={{ padding: space.lg }}>
          {!!p.brand_name && <Text style={{ ...type.caption, color: colors.textMuted }}>{p.brand_name}</Text>}
          <Text style={{ ...type.title, color: colors.text, marginTop: 2 }}>{p.name}</Text>
          <Text style={{ ...type.body, color: colors.textMuted, marginTop: 2 }}>{p.selling_unit}</Text>

          <View style={{ flexDirection: "row", alignItems: "center", marginTop: space.md }}>
            <Text style={{ ...type.display, color: colors.text }}>{formatPrice(p.selling_price)}</Text>
            {hasDiscount && (
              <>
                <Text
                  style={{ ...type.body, color: colors.textMuted, marginLeft: space.sm, textDecorationLine: "line-through" }}
                >
                  {formatPrice(p.mrp)}
                </Text>
                <View
                  style={{
                    marginLeft: space.sm,
                    backgroundColor: colors.marigold,
                    borderRadius: radius.sm,
                    paddingHorizontal: space.sm,
                    paddingVertical: 2,
                  }}
                >
                  <Text style={{ ...type.caption, color: colors.onMarigold }}>{p.discount_percent}% off</Text>
                </View>
              </>
            )}
          </View>

          {p.only_left != null && (
            <Text style={{ ...type.body, color: colors.danger, marginTop: space.sm }}>Sirf {p.only_left} bache hain</Text>
          )}

          {!!p.description && (
            <>
              <Text style={{ ...type.heading, color: colors.text, marginTop: space.xl }}>Jaankari</Text>
              <Text style={{ ...type.body, color: colors.textMuted, marginTop: space.xs }}>{p.description}</Text>
            </>
          )}

          {/* Dukaan ka link */}
          <Pressable
            onPress={() => router.push({ pathname: "/store/[id]", params: { id: p.store.id } })}
            style={({ pressed }) => ({
              flexDirection: "row",
              alignItems: "center",
              backgroundColor: colors.surface,
              borderWidth: 1,
              borderColor: colors.line,
              borderRadius: radius.md,
              padding: space.lg,
              marginTop: space.xl,
              opacity: pressed ? 0.9 : 1,
            })}
          >
            <View style={{ flex: 1 }}>
              <Text style={{ ...type.caption, color: colors.textMuted }}>{isFood ? "Restaurant" : "Dukaan"}</Text>
              <Text style={{ ...type.heading, color: colors.text }}>{p.store.name}</Text>
              <Text style={{ ...type.caption, color: colors.textMuted }}>
                {p.distance_km.toFixed(1)} km · {p.eta_minutes} min
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={20} color={colors.textMuted} />
          </Pressable>
        </View>
      </ScrollView>
            {/* Neeche ka bar: cart me daalna */}
      <View
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: 0,
          flexDirection: "row",
          alignItems: "center",
          backgroundColor: colors.surface,
          borderTopWidth: 1,
          borderTopColor: colors.line,
          padding: space.lg,
          paddingBottom: insets.bottom + space.md,
        }}
      >
        <View style={qtyOf(p.id) > 0 ? { width: 150 } : { flex: 1 }}>
          <QtyControl productId={p.id} large />
        </View>
        {qtyOf(p.id) > 0 && (
          <Pressable
            onPress={() => router.push("/cart")}
            style={{
              flex: 1,
              marginLeft: space.md,
              height: 48,
              borderRadius: radius.pill,
              backgroundColor: colors.ink,
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Text style={{ ...type.heading, color: colors.onInk }}>
              Cart dekhein{cart ? ` · ${formatPrice(cart.subtotal)}` : ""}
            </Text>
          </Pressable>
        )}
      </View>
    </View>
  );
}