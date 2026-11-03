import { useCallback, useState } from "react";
import { ActivityIndicator, FlatList, Pressable, RefreshControl, Text, View } from "react-native";
import { useFocusEffect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { errorMessage } from "../src/api/client";
import { listOrders, OrderSummary } from "../src/api/orders";
import { IconButton } from "../src/components/IconButton";
import { StatusBadge } from "../src/components/StatusBadge";
import { formatDateTime } from "../src/lib/orderUi";
import { formatPrice } from "../src/lib/media";
import { colors, radius, space, type } from "../src/theme";

const PAGE = 20;

export default function Orders() {
  const router = useRouter();
  const insets = useSafeAreaInsets();

  const [items, setItems] = useState<OrderSummary[] | null>(null);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);

  const load = useCallback(async () => {
    setError("");
    try {
      const first = await listOrders(PAGE, 0);
      setItems(first);
      setHasMore(first.length === PAGE);
    } catch (e) {
      setError(errorMessage(e));
    }
  }, []);

  // Order page se wapas aane par bhi list taza ho jaye (status badla ho sakta hai)
  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const loadMore = async () => {
    if (!items || loadingMore || !hasMore) return;
    setLoadingMore(true);
    try {
      const next = await listOrders(PAGE, items.length);
      setItems([...items, ...next]);
      setHasMore(next.length === PAGE);
    } catch {
      setHasMore(false);
    } finally {
      setLoadingMore(false);
    }
  };

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
        <Text style={{ ...type.title, color: colors.onInk, marginLeft: space.md }}>Aapke orders</Text>
      </View>

      {error ? (
        <View style={{ flex: 1, alignItems: "center", justifyContent: "center", padding: space.xl }}>
          <Text style={{ ...type.body, color: colors.danger, textAlign: "center" }}>{error}</Text>
          <Pressable onPress={load} style={{ marginTop: space.lg }}>
            <Text style={{ ...type.heading, color: colors.ink }}>Dobara try karein</Text>
          </Pressable>
        </View>
      ) : items === null ? (
        <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
          <ActivityIndicator color={colors.ink} />
        </View>
      ) : (
        <FlatList
          data={items}
          keyExtractor={(o) => o.id}
          contentContainerStyle={{ padding: space.lg, paddingBottom: insets.bottom + space.xl }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.ink} />}
          onEndReached={loadMore}
          onEndReachedThreshold={0.5}
          ListEmptyComponent={
            <View style={{ alignItems: "center", paddingTop: space.xxl }}>
              <Text style={{ ...type.title, color: colors.text }}>Abhi koi order nahi hai</Text>
              <Text style={{ ...type.body, color: colors.textMuted, marginTop: space.xs, textAlign: "center" }}>
                Paas ki dukaanon se pehla order karke dekhein.
              </Text>
            </View>
          }
          ListFooterComponent={loadingMore ? <ActivityIndicator color={colors.ink} style={{ margin: space.lg }} /> : null}
          renderItem={({ item }) => (
            <Pressable
              onPress={() => router.push({ pathname: "/order/[id]", params: { id: item.id } })}
              style={({ pressed }) => ({
                backgroundColor: colors.surface,
                borderWidth: 1,
                borderColor: colors.line,
                borderRadius: radius.md,
                padding: space.lg,
                marginBottom: space.md,
                opacity: pressed ? 0.92 : 1,
              })}
            >
              <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
                <Text style={{ ...type.heading, color: colors.text }}>{item.order_number}</Text>
                <StatusBadge status={item.status} />
              </View>
              <Text numberOfLines={1} style={{ ...type.body, color: colors.textMuted, marginTop: space.xs }}>
                {item.store_names.join(", ")}
              </Text>
              <View style={{ flexDirection: "row", justifyContent: "space-between", marginTop: space.sm }}>
                <Text style={{ ...type.caption, color: colors.textMuted }}>
                  {item.item_count} item · {formatDateTime(item.created_at)}
                </Text>
                <Text style={{ ...type.heading, color: colors.text }}>{formatPrice(item.total)}</Text>
              </View>
              {item.has_removed_items && (
                <Text style={{ ...type.caption, color: colors.marigoldDeep, marginTop: space.xs }}>
                  Kuch saman nahi mila. Detail dekhein.
                </Text>
              )}
            </Pressable>
          )}
        />
      )}
    </View>
  );
}