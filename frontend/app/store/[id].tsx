import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, FlatList, Image, Pressable, ScrollView, Text, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { FloatingCartBar } from "../../src/components/FloatingCartBar";
import { errorMessage } from "../../src/api/client";
import {
  fetchStore,
  fetchStoreCategories,
  listProducts,
  ProductCard,
  StoreCategory,
  StoreDetail,
} from "../../src/api/shop";
import { fixMediaUrl, formatPrice } from "../../src/lib/media";
import { storeCategoryLabel } from "../../src/lib/storeCategories";
import { IconButton } from "../../src/components/IconButton";
import { ProductCardView } from "../../src/components/ProductCardView";
import { useFavourites } from "../../src/favourites/FavouritesContext";
import { useCoords } from "../../src/lib/LocationContext";
import { colors, radius, space, type } from "../../src/theme";

const PAGE = 20;

export default function StoreScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const coords = useCoords();
  const fav = useFavourites();

  const [store, setStore] = useState<StoreDetail | null>(null);
  const [cats, setCats] = useState<StoreCategory[]>([]);
  const [catId, setCatId] = useState<string | undefined>(undefined);
  const [products, setProducts] = useState<ProductCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [productsLoading, setProductsLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState("");

  const lat = coords?.lat;
  const lng = coords?.lng;

  const loadStore = useCallback(async () => {
    if (lat == null || lng == null || !id) return;
    setLoading(true);
    setError("");
    try {
      const geo = { lat, lng };
      const [s, c] = await Promise.all([fetchStore(id, geo), fetchStoreCategories(id, geo)]);
      setStore(s);
      setCats(c);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [id, lat, lng]);

  useEffect(() => {
    loadStore();
  }, [loadStore]);

  // Category badalne par products dobara
  useEffect(() => {
    if (lat == null || lng == null || !id) return;
    (async () => {
      setProductsLoading(true);
      try {
        const p = await listProducts({ lat, lng, store_id: id, category_id: catId, limit: PAGE, offset: 0 });
        setProducts(p);
        setHasMore(p.length === PAGE);
      } catch {
        setProducts([]);
        setHasMore(false);
      } finally {
        setProductsLoading(false);
      }
    })();
  }, [id, lat, lng, catId]);

  const loadMore = async () => {
    if (lat == null || lng == null || !id || loadingMore || productsLoading || !hasMore) return;
    setLoadingMore(true);
    try {
      const next = await listProducts({
        lat,
        lng,
        store_id: id,
        category_id: catId,
        limit: PAGE,
        offset: products.length,
      });
      setProducts((prev) => [...prev, ...next]);
      setHasMore(next.length === PAGE);
    } catch {
      setHasMore(false);
    } finally {
      setLoadingMore(false);
    }
  };

  const topBar = (
    <View
      style={{
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "space-between",
        backgroundColor: colors.ink,
        paddingTop: insets.top + space.sm,
        paddingHorizontal: space.lg,
        paddingBottom: space.md,
      }}
    >
      <IconButton name="arrow-back" onPress={() => (router.canGoBack() ? router.back() : router.replace("/"))} />
      {store && (
        <IconButton
          name={fav.isStoreFav(store.id) ? "heart" : "heart-outline"}
          color={fav.isStoreFav(store.id) ? colors.danger : colors.text}
          onPress={() => fav.toggleStore(store.id)}
        />
      )}
    </View>
  );

  if (loading || !coords) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.canvas }}>
        {topBar}
        <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
          <ActivityIndicator color={colors.ink} />
        </View>
      </View>
    );
  }

  if (error || !store) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.canvas }}>
        {topBar}
        <View style={{ flex: 1, alignItems: "center", justifyContent: "center", padding: space.xl }}>
          <Text style={{ ...type.body, color: colors.danger, textAlign: "center" }}>{error || "Dukaan nahi mili."}</Text>
          <Pressable onPress={loadStore} style={{ marginTop: space.lg }}>
            <Text style={{ ...type.heading, color: colors.ink }}>Dobara try karein</Text>
          </Pressable>
        </View>
      </View>
    );
  }

  const isFood = store.store_type === "RESTAURANT";
  const open = store.shop_status === "OPEN";

  const header = (
    <View>
      {!!store.image_medium_url && (
        <Image source={{ uri: fixMediaUrl(store.image_medium_url) || undefined }} style={{ width: "100%", height: 190, borderRadius: radius.md, marginBottom: space.md, backgroundColor: colors.canvas }} resizeMode="cover" />
      )}
      <View style={{ flexDirection: "row", alignItems: "center" }}>
        <View
          style={{
            backgroundColor: isFood ? "#FCE9C2" : "#D9EBE8",
            paddingHorizontal: space.sm,
            paddingVertical: 2,
            borderRadius: radius.pill,
          }}
        >
          <Text style={{ ...type.caption, color: isFood ? colors.marigoldDeep : colors.inkSoft }}>
            {storeCategoryLabel(store.store_category)}
          </Text>
        </View>
        <View
          style={{
            marginLeft: space.sm,
            backgroundColor: open ? "#DDF1E4" : "#F7DAD7",
            paddingHorizontal: space.sm,
            paddingVertical: 2,
            borderRadius: radius.pill,
          }}
        >
          <Text style={{ ...type.caption, color: open ? colors.success : colors.danger }}>
            {open ? "Khuli hai" : "Band hai"}
          </Text>
        </View>
      </View>

      <Text style={{ ...type.display, color: colors.text, marginTop: space.sm }}>{store.name}</Text>
      {!!(store.cuisine || store.description) && (
        <Text style={{ ...type.body, color: colors.textMuted, marginTop: space.xs }}>
          {store.cuisine || store.description}
        </Text>
      )}

      <Text style={{ ...type.body, color: colors.text, marginTop: space.md }}>
        {store.distance_km.toFixed(1)} km · {store.eta_minutes} min
        {store.min_order_amount > 0 ? ` · Kam se kam ${formatPrice(store.min_order_amount)}` : ""}
      </Text>
      <Text style={{ ...type.caption, color: colors.textMuted, marginTop: space.xs }}>{store.address}</Text>

      {!store.can_order && (
        <View
          style={{
            backgroundColor: "#FBEFD0",
            borderRadius: radius.md,
            padding: space.md,
            marginTop: space.lg,
          }}
        >
          <Text style={{ ...type.body, color: colors.onMarigold }}>
            {!store.deliverable
              ? "Ye dukaan aapke area me deliver nahi karti."
              : "Dukaan abhi band hai. Aap saman dekh sakte hain, order khulne par kar paayenge."}
          </Text>
        </View>
      )}

      {cats.length > 0 && (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={{ marginTop: space.lg, marginHorizontal: -space.lg }}
          contentContainerStyle={{ paddingHorizontal: space.lg }}
        >
          {[{ id: undefined as string | undefined, name: "Sab", product_count: 0 }, ...cats].map((c) => {
            const on = catId === c.id;
            return (
              <Pressable
                key={c.id ?? "all"}
                onPress={() => setCatId(c.id)}
                style={{
                  backgroundColor: on ? colors.ink : colors.surface,
                  borderWidth: 1,
                  borderColor: on ? colors.ink : colors.line,
                  borderRadius: radius.pill,
                  paddingHorizontal: space.lg,
                  paddingVertical: space.sm,
                  marginRight: space.sm,
                }}
              >
                <Text style={{ ...type.body, color: on ? colors.onInk : colors.text }}>
                  {c.name}
                  {c.id ? ` (${c.product_count})` : ""}
                </Text>
              </Pressable>
            );
          })}
        </ScrollView>
      )}

      <Text style={{ ...type.heading, color: colors.text, marginTop: space.xl, marginBottom: space.md }}>Products</Text>
      {productsLoading && <ActivityIndicator color={colors.ink} style={{ marginBottom: space.lg }} />}
    </View>
  );

  return (
    <View style={{ flex: 1, backgroundColor: colors.canvas }}>
      {topBar}
      <FlatList
        data={productsLoading ? [] : products}
        keyExtractor={(p) => p.id}
        numColumns={2}
        columnWrapperStyle={{ justifyContent: "space-between", marginBottom: space.md }}
        ListHeaderComponent={header}
        ListEmptyComponent={
          productsLoading ? null : (
            <Text style={{ ...type.body, color: colors.textMuted }}>Is category me abhi koi product nahi hai.</Text>
          )
        }
        ListFooterComponent={loadingMore ? <ActivityIndicator color={colors.ink} style={{ margin: space.lg }} /> : null}
        renderItem={({ item }) => (
          <ProductCardView
            product={item}
            onPress={() => router.push({ pathname: "/product/[id]", params: { id: item.id } })}
          />
        )}
        onEndReached={loadMore}
        onEndReachedThreshold={0.5}
        contentContainerStyle={{
          paddingHorizontal: space.lg,
          paddingTop: space.lg,
          paddingBottom: insets.bottom + space.xl,
        }}
      />
      <FloatingCartBar />
    </View>
  );
}
