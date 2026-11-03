import { useCallback, useState } from "react";
import { FlatList, Image, Pressable, RefreshControl, Text, View } from "react-native";
import { useFocusEffect, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { errorMessage } from "../../../src/api/client";
import { ProductStatus, listProducts, SellerProduct } from "../../../src/api/sellerProducts";
import { Button } from "../../../src/components/Button";
import { Badge, Chips, EmptyState, ErrorText, SellerHeader, Spinner } from "../../../src/components/seller/ui";
import { fixMediaUrl, formatPrice } from "../../../src/lib/media";
import { PRODUCT_STATUS } from "../../../src/seller/productUi";
import { useSeller } from "../../../src/seller/SellerContext";
import { colors, radius, space, type } from "../../../src/theme";

const PAGE = 30;

type Filter = ProductStatus | "ALL";
const FILTERS: { value: Filter; label: string }[] = [
  { value: "ALL", label: "Sab" },
  { value: "PENDING_APPROVAL", label: "Review me" },
  { value: "ACTIVE", label: "Live" },
  { value: "OUT_OF_STOCK", label: "Stock khatam" },
  { value: "INACTIVE", label: "Chhupe" },
  { value: "REJECTED", label: "Reject" },
];

export default function SellerProducts() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { store } = useSeller();

  const [filter, setFilter] = useState<Filter>("ALL");
  const [items, setItems] = useState<SellerProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState("");

  const storeId = store?.id;

  const load = useCallback(
    async (f: Filter) => {
      if (!storeId) return;
      setError("");
      try {
        const rows = await listProducts(storeId, f === "ALL" ? undefined : f, PAGE, 0);
        setItems(rows);
        setHasMore(rows.length === PAGE);
      } catch (e) {
        setError(errorMessage(e));
      } finally {
        setLoading(false);
      }
    },
    [storeId],
  );

  // Edit karke wapas aane par list taza
  useFocusEffect(
    useCallback(() => {
      load(filter);
    }, [load, filter]),
  );

  const pickFilter = (f: Filter) => {
    setLoading(true);
    setFilter(f);
  };

  const loadMore = async () => {
    if (!storeId || loadingMore || !hasMore) return;
    setLoadingMore(true);
    try {
      const rows = await listProducts(storeId, filter === "ALL" ? undefined : filter, PAGE, items.length);
      setItems((prev) => [...prev, ...rows]);
      setHasMore(rows.length === PAGE);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoadingMore(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await load(filter);
    setRefreshing(false);
  };

  if (!store) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.canvas }}>
        <SellerHeader title="Saman" onBack={() => (router.canGoBack() ? router.back() : router.replace("/seller"))} />
        <EmptyState
          title="Pehle dukaan banayein"
          body="Saman dukaan ke andar jodte hain."
          action={<Button label="Dukaan banayein" onPress={() => router.replace("/seller/store")} />}
        />
      </View>
    );
  }

  return (
    <View style={{ flex: 1, backgroundColor: colors.canvas }}>
      <SellerHeader
        title="Saman"
        subtitle={store.name}
        onBack={() => (router.canGoBack() ? router.back() : router.replace("/seller"))}
        right={
          <Pressable
            onPress={() => router.push("/seller/products/new")}
            hitSlop={8}
            style={{
              flexDirection: "row",
              alignItems: "center",
              backgroundColor: colors.marigold,
              borderRadius: radius.pill,
              paddingHorizontal: space.md,
              paddingVertical: 6,
            }}
          >
            <Ionicons name="add" size={20} color={colors.onMarigold} />
            <Text style={{ ...type.body, color: colors.onMarigold }}>Naya</Text>
          </Pressable>
        }
      />
      <View style={{ paddingVertical: space.md }}>
        <Chips options={FILTERS} value={filter} onChange={pickFilter} />
      </View>

      {loading ? (
        <Spinner />
      ) : (
        <FlatList
          data={items}
          keyExtractor={(p) => p.id}
          contentContainerStyle={{ padding: space.lg, paddingTop: 0, paddingBottom: insets.bottom + space.xxl }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.ink} />}
          onEndReached={loadMore}
          onEndReachedThreshold={0.4}
          ListHeaderComponent={<ErrorText>{error}</ErrorText>}
          ListEmptyComponent={
            error ? null : (
              <EmptyState
                title={filter === "ALL" ? "Abhi koi saman nahi jura" : "Is tarah ka koi saman nahi"}
                body={filter === "ALL" ? "Pehla saman jodein, photo lagayein. Admin approve karega to customer ko dikhega." : undefined}
                action={filter === "ALL" ? <Button label="Saman jodein" onPress={() => router.push("/seller/products/new")} /> : undefined}
              />
            )
          }
          ListFooterComponent={loadingMore ? <Spinner /> : null}
          renderItem={({ item: p }) => {
            const st = PRODUCT_STATUS[p.status];
            const img = fixMediaUrl(p.images[0]?.thumb_url);
            return (
              <Pressable
                onPress={() => router.push({ pathname: "/seller/products/[id]", params: { id: p.id } })}
                style={({ pressed }) => ({
                  flexDirection: "row",
                  backgroundColor: colors.surface,
                  borderWidth: 1,
                  borderColor: colors.line,
                  borderRadius: radius.md,
                  padding: space.md,
                  marginBottom: space.sm,
                  opacity: pressed ? 0.9 : 1,
                })}
              >
                <View
                  style={{
                    width: 64,
                    height: 64,
                    borderRadius: radius.sm,
                    backgroundColor: "#EDF2F1",
                    overflow: "hidden",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  {img ? (
                    <Image source={{ uri: img }} style={{ width: 64, height: 64 }} resizeMode="cover" />
                  ) : (
                    <Ionicons name="image-outline" size={24} color={colors.textMuted} />
                  )}
                </View>
                <View style={{ flex: 1, marginLeft: space.md }}>
                  <Text style={{ ...type.heading, color: colors.text }} numberOfLines={1}>
                    {p.name}
                  </Text>
                  <Text style={{ ...type.caption, color: colors.textMuted }}>
                    {p.selling_unit} · {formatPrice(p.selling_price)}
                    {p.mrp > p.selling_price ? `  (MRP ${formatPrice(p.mrp)})` : ""}
                  </Text>
                  <Text style={{ ...type.caption, color: colors.textMuted, marginTop: 2 }}>
                    Commission: {p.commission_mode === "FIXED" ? `${formatPrice(p.commission_value)} × ${p.commission_unit_quantity} ${p.commission_unit}` : `${p.commission_value}% (${p.commission_unit})`}
                  </Text>
                  <View style={{ flexDirection: "row", alignItems: "center", marginTop: 4 }}>
                    <Badge label={st.label} tone={st.tone} />
                    <Text
                      style={{
                        ...type.caption,
                        marginLeft: space.sm,
                        color: p.stock === 0 || p.low_stock ? colors.danger : colors.textMuted,
                      }}
                    >
                      Stock {p.stock}
                      {p.stock > 0 && p.low_stock ? " (kam)" : ""}
                    </Text>
                  </View>
                </View>
              </Pressable>
            );
          }}
        />
      )}
    </View>
  );
}
