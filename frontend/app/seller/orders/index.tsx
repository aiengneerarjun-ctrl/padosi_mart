import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { FlatList, Pressable, RefreshControl, Text, View } from "react-native";
import { useFocusEffect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { errorMessage } from "../../../src/api/client";
import { listSellerOrders, SellerOrder } from "../../../src/api/sellerOrders";
import { Badge, Chips, EmptyState, ErrorText, SellerHeader, Spinner } from "../../../src/components/seller/ui";
import { formatPrice } from "../../../src/lib/media";
import { formatDateTime } from "../../../src/lib/orderUi";
import { GROUP_OF, OrderGroup, paymentLabel, STORE_ORDER_STATUS } from "../../../src/seller/orderUi";
import { colors, radius, space, type } from "../../../src/theme";

const POLL_MS = 20000; // naye order jaldi dikhein, isliye har 20 second me taza

const EMPTY_TEXT: Record<OrderGroup, string> = {
  new: "Abhi koi naya order nahi hai",
  active: "Abhi koi order taiyaar nahi ho raha",
  ready: "Koi order delivery partner ka intezaar nahi kar raha",
  past: "Abhi koi purana order nahi hai",
};

export default function SellerOrders() {
  const router = useRouter();
  const insets = useSafeAreaInsets();

  const [orders, setOrders] = useState<SellerOrder[]>([]);
  const [group, setGroup] = useState<OrderGroup>("new");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const firstPick = useRef(true);

  const load = useCallback(async () => {
    try {
      setOrders(await listSellerOrders(undefined, 100, 0));
      setError("");
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  // Screen dikh rahi ho tabhi taza karte raho
  useFocusEffect(
    useCallback(() => {
      load();
      const t = setInterval(load, POLL_MS);
      return () => clearInterval(t);
    }, [load]),
  );

  const counts = useMemo(() => {
    const c: Record<OrderGroup, number> = { new: 0, active: 0, ready: 0, past: 0 };
    for (const o of orders) c[GROUP_OF[o.status]] += 1;
    return c;
  }, [orders]);

  // Pehli baar naye order na hon par chalu order ho to wahi dikha do
  useEffect(() => {
    if (!loading && firstPick.current) {
      firstPick.current = false;
      if (counts.new === 0 && counts.active > 0) setGroup("active");
    }
  }, [loading, counts]);

  const shown = orders.filter((o) => GROUP_OF[o.status] === group);

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.canvas }}>
      <SellerHeader title="Orders" subtitle="Naye order yahan apne aap aate hain" onBack={() => (router.canGoBack() ? router.back() : router.replace("/seller"))} />
      <View style={{ paddingVertical: space.md }}>
        <Chips
          value={group}
          onChange={setGroup}
          options={[
            { value: "new" as OrderGroup, label: "Naye", count: counts.new },
            { value: "active" as OrderGroup, label: "Chal rahe", count: counts.active },
            { value: "ready" as OrderGroup, label: "Ready", count: 0 },
            { value: "past" as OrderGroup, label: "Purane", count: 0 },
          ]}
        />
      </View>

      {loading ? (
        <Spinner />
      ) : (
        <FlatList
          data={shown}
          keyExtractor={(o) => o.id}
          contentContainerStyle={{ padding: space.lg, paddingTop: 0, paddingBottom: insets.bottom + space.xxl }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.ink} />}
          ListHeaderComponent={<ErrorText>{error}</ErrorText>}
          ListEmptyComponent={error ? null : <EmptyState title={EMPTY_TEXT[group]} />}
          renderItem={({ item: o }) => {
            const st = STORE_ORDER_STATUS[o.status];
            const live = o.items.filter((i) => !i.removed);
            return (
              <Pressable
                onPress={() => router.push({ pathname: "/seller/orders/[id]", params: { id: o.id } })}
                style={({ pressed }) => ({
                  backgroundColor: colors.surface,
                  borderWidth: o.status === "PLACED" ? 2 : 1,
                  borderColor: o.status === "PLACED" ? colors.marigold : colors.line,
                  borderRadius: radius.md,
                  padding: space.lg,
                  marginBottom: space.sm,
                  opacity: pressed ? 0.9 : 1,
                })}
              >
                <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
                  <Text style={{ ...type.heading, color: colors.text }}>#{o.order_number}</Text>
                  <Text style={{ ...type.caption, color: colors.textMuted }}>{formatDateTime(o.created_at)}</Text>
                </View>
                <Text style={{ ...type.body, color: colors.textMuted, marginTop: 2 }} numberOfLines={2}>
                  {live.length === 0
                    ? "Saare items hat gaye"
                    : live.map((i) => `${i.name} × ${i.quantity}`).join(", ")}
                </Text>
                <View style={{ flexDirection: "row", alignItems: "center", marginTop: space.sm }}>
                  <Badge label={st.label} tone={st.tone} />
                  <View style={{ width: space.sm }} />
                  <Badge label={paymentLabel(o.payment_method)} />
                  <Text style={{ ...type.heading, color: colors.text, flex: 1, textAlign: "right" }}>
                    {formatPrice(o.items_subtotal)}
                  </Text>
                </View>
              </Pressable>
            );
          }}
        />
      )}
    </View>
  );
}
