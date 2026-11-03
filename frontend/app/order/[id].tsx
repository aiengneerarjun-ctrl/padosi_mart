import { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, Alert, Pressable, RefreshControl, ScrollView, Text, View } from "react-native";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { errorMessage } from "../../src/api/client";
import { cancelOrder, getOrder, OrderOut } from "../../src/api/orders";
import { IconButton } from "../../src/components/IconButton";
import { StatusBadge } from "../../src/components/StatusBadge";
import { formatDateTime, isActiveOrder, statusLabel } from "../../src/lib/orderUi";
import { formatPrice } from "../../src/lib/media";
import { colors, radius, space, type } from "../../src/theme";

function Card({ children, tint }: { children: React.ReactNode; tint?: string }) {
  return (
    <View
      style={{
        backgroundColor: tint ?? colors.surface,
        borderWidth: tint ? 0 : 1,
        borderColor: colors.line,
        borderRadius: radius.md,
        padding: space.lg,
        marginBottom: space.md,
      }}
    >
      {children}
    </View>
  );
}

function BillRow({ label, value, color, bold }: { label: string; value: string; color?: string; bold?: boolean }) {
  return (
    <View style={{ flexDirection: "row", justifyContent: "space-between", paddingVertical: 4 }}>
      <Text style={{ ...(bold ? type.heading : type.body), color: bold ? colors.text : colors.textMuted }}>{label}</Text>
      <Text style={{ ...(bold ? type.heading : type.body), color: color ?? colors.text }}>{value}</Text>
    </View>
  );
}

function paymentText(o: OrderOut): string {
  if (o.payment_method === "COD") {
    if (o.status === "CANCELLED") return "Cash on delivery. Order cancel hai, kuch dena nahi.";
    return o.amount_due > 0 ? `Delivery par ${formatPrice(o.amount_due)} cash dein.` : "Cash on delivery.";
  }
  if (o.payment_status === "PAID") return "Online payment ho chuki hai.";
  if (o.payment_status === "PENDING") return "Online payment baaki hai.";
  return `Online payment: ${o.payment_status}`;
}

export default function OrderScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const insets = useSafeAreaInsets();

  const [order, setOrder] = useState<OrderOut | null>(null);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [cancelling, setCancelling] = useState(false);

  const liveRef = useRef(true);

  const load = useCallback(
    async (silent = false) => {
      if (!id) return;
      try {
        const o = await getOrder(id);
        setOrder(o);
        liveRef.current = isActiveOrder(o.status);
        setError("");
      } catch (e) {
        if (!silent) setError(errorMessage(e));
      }
    },
    [id],
  );

  // Screen dikh rahi ho aur order chal raha ho to har 15 second me status taza karo
  useFocusEffect(
    useCallback(() => {
      load();
      const t = setInterval(() => {
        if (liveRef.current) load(true);
      }, 15000);
      return () => clearInterval(t);
    }, [load]),
  );

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const confirmCancel = () =>
    Alert.alert("Order cancel karein?", "Dukaan ne abhi order accept nahi kiya, isliye cancel ho sakta hai.", [
      { text: "Nahi", style: "cancel" },
      {
        text: "Haan, cancel karein",
        style: "destructive",
        onPress: async () => {
          if (!id) return;
          setCancelling(true);
          try {
            setOrder(await cancelOrder(id));
          } catch (e) {
            Alert.alert("Order", errorMessage(e));
            load();
          } finally {
            setCancelling(false);
          }
        },
      },
    ]);

  const topBar = (
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
      <Text style={{ ...type.title, color: colors.onInk, marginLeft: space.md }}>
        {order ? `Order ${order.order_number}` : "Order"}
      </Text>
    </View>
  );

  if (!order) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.canvas }}>
        {topBar}
        <View style={{ flex: 1, alignItems: "center", justifyContent: "center", padding: space.xl }}>
          {error ? (
            <>
              <Text style={{ ...type.body, color: colors.danger, textAlign: "center" }}>{error}</Text>
              <Pressable onPress={() => load()} style={{ marginTop: space.lg }}>
                <Text style={{ ...type.heading, color: colors.ink }}>Dobara try karein</Text>
              </Pressable>
            </>
          ) : (
            <ActivityIndicator color={colors.ink} />
          )}
        </View>
      </View>
    );
  }

  // Sirf poore order ke badlav (dukaan-wise detail ke baar-baar wale entries nahi)
  const timeline = order.history.filter((h) => h.store_order_id === null).slice().reverse();

  return (
    <View style={{ flex: 1, backgroundColor: colors.canvas }}>
      {topBar}
      <ScrollView
        contentContainerStyle={{ padding: space.lg, paddingBottom: insets.bottom + space.xxl }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.ink} />}
        showsVerticalScrollIndicator={false}
      >
        {/* Status */}
        <Card>
          <StatusBadge status={order.status} />
          <Text style={{ ...type.title, color: colors.text, marginTop: space.sm }}>{statusLabel(order.status)}</Text>
          <Text style={{ ...type.caption, color: colors.textMuted, marginTop: 2 }}>
            {formatDateTime(order.created_at)} par order kiya
          </Text>
          <Text style={{ ...type.body, color: colors.text, marginTop: space.sm }}>{paymentText(order)}</Text>
        </Card>
                {/* Online payment baaki ho to */}
        {order.payment_method === "ONLINE" && order.payment_status === "PENDING" && order.status === "PLACED" && (
          <Card tint="#FBEFD0">
            <Text style={{ ...type.body, color: colors.onMarigold }}>
              Online payment baaki hai.
              {order.payment_expires_at
                ? ` ${formatDateTime(order.payment_expires_at)} se pehle payment karein, warna order cancel ho jayega.`
                : ""}
            </Text>
            <Pressable
              onPress={() => router.push({ pathname: "/pay/[id]", params: { id: order.id } })}
              style={{
                marginTop: space.md,
                height: 48,
                borderRadius: radius.pill,
                backgroundColor: colors.marigold,
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Text style={{ ...type.heading, color: colors.onMarigold }}>
                Abhi payment karein · {formatPrice(order.total)}
              </Text>
            </Pressable>
          </Card>
        )}

        {/* Delivery OTP */}
        {!!order.delivery_otp && (
          <Card tint={colors.ink}>
            <Text style={{ ...type.body, color: "#B9D3CF" }}>Delivery partner ko ye OTP batayein</Text>
            <Text style={{ ...type.display, color: colors.marigold, letterSpacing: 10, marginTop: space.xs }}>
              {order.delivery_otp}
            </Text>
          </Card>
        )}

        {/* Seller ne kuch hataya ho */}
        {!!order.notice && (
          <Card tint="#FBEFD0">
            <Text style={{ ...type.body, color: colors.onMarigold }}>{order.notice}</Text>
          </Card>
        )}
        {order.removed_items.length > 0 && (
          <Card>
            <Text style={{ ...type.heading, color: colors.text }}>Ye saman nahi mila</Text>
            {order.removed_items.map((r, i) => (
              <View key={`${r.product_id}-${i}`} style={{ marginTop: space.sm }}>
                <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
                  <Text style={{ ...type.body, color: colors.text, flex: 1, paddingRight: space.md }}>
                    {r.name} × {r.quantity}
                  </Text>
                  <Text style={{ ...type.body, color: colors.danger }}>- {formatPrice(r.line_total)}</Text>
                </View>
                <Text style={{ ...type.caption, color: colors.textMuted }}>
                  {r.store_name} · {r.reason}
                  {r.kept_quantity ? ` · ${r.kept_quantity} piece mil gaye` : ""}
                </Text>
                {!!r.note && <Text style={{ ...type.caption, color: colors.textMuted }}>{r.note}</Text>}
              </View>
            ))}
          </Card>
        )}

        {/* Dukaan-wise saman */}
        {order.stores.map((s) => (
          <Card key={s.id}>
            <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
              <Text style={{ ...type.heading, color: colors.text, flex: 1 }}>{s.store_name}</Text>
              <StatusBadge status={s.status} />
            </View>
            <Text style={{ ...type.caption, color: colors.textMuted }}>{s.store_address}</Text>
            {s.items.map((it) => (
              <View
                key={it.product_id}
                style={{ flexDirection: "row", justifyContent: "space-between", marginTop: space.sm }}
              >
                <Text
                  style={{
                    ...type.body,
                    flex: 1,
                    paddingRight: space.md,
                    color: it.removed ? colors.textMuted : colors.text,
                    textDecorationLine: it.removed ? "line-through" : "none",
                  }}
                >
                  {it.name} × {it.quantity}
                </Text>
                <Text
                  style={{
                    ...type.body,
                    color: it.removed ? colors.textMuted : colors.text,
                    textDecorationLine: it.removed ? "line-through" : "none",
                  }}
                >
                  {formatPrice(it.line_total)}
                </Text>
              </View>
            ))}
          </Card>
        ))}

        {/* Bill */}
        <Card>
          <Text style={{ ...type.heading, color: colors.text, marginBottom: space.xs }}>Bill</Text>
          <BillRow label="Saman ka total" value={formatPrice(order.items_subtotal)} />
          <BillRow
            label="Delivery charge"
            value={order.delivery_fee > 0 ? formatPrice(order.delivery_fee) : "Free"}
            color={order.delivery_fee > 0 ? undefined : colors.success}
          />
          {order.discount_amount > 0 && (
            <BillRow
              label={`Coupon${order.coupon_code ? ` (${order.coupon_code})` : ""}`}
              value={`- ${formatPrice(order.discount_amount)}`}
              color={colors.success}
            />
          )}
          <View style={{ height: 1, backgroundColor: colors.line, marginVertical: space.sm }} />
          <BillRow label="Kul total" value={formatPrice(order.total)} bold />
          {order.removed_total > 0 && (
            <Text style={{ ...type.caption, color: colors.textMuted, marginTop: space.xs }}>
              Pehle ka total {formatPrice(order.original_total)} tha. Hataye gaye saman ke paise kam ho gaye.
            </Text>
          )}
          {order.refunded_total > 0 && (
            <Text style={{ ...type.caption, color: colors.success, marginTop: space.xs }}>
              {formatPrice(order.refunded_total)} wapas kiya gaya (ya wapas ho raha hai).
            </Text>
          )}
        </Card>

        {/* Address */}
        <Card>
          <Text style={{ ...type.caption, color: colors.textMuted }}>Delivery address</Text>
          <Text style={{ ...type.heading, color: colors.text }}>
            {order.address.receiver_name} · {order.address.receiver_phone}
          </Text>
          <Text style={{ ...type.body, color: colors.textMuted }}>{order.address.address_line}</Text>
          {!!order.address.landmark && (
            <Text style={{ ...type.caption, color: colors.textMuted }}>Landmark: {order.address.landmark}</Text>
          )}
          {!!order.note && (
            <Text style={{ ...type.caption, color: colors.textMuted, marginTop: space.xs }}>Aapka note: {order.note}</Text>
          )}
        </Card>

        {/* Status ka itihaas */}
        {timeline.length > 0 && (
          <Card>
            <Text style={{ ...type.heading, color: colors.text }}>Order ka safar</Text>
            {timeline.map((h, i) => (
              <View key={`${h.to_status}-${h.created_at}-${i}`} style={{ flexDirection: "row", minHeight: 64, marginTop: space.md }}>
                <View
                  style={{
                    width: 12,
                    alignItems: "center",
                    marginTop: 6,
                  }}
                >
                  <View
                    style={{
                      width: 10,
                      height: 10,
                      borderRadius: 5,
                      backgroundColor: colors.ink,
                    }}
                  />
                  {i < timeline.length - 1 && (
                    <View style={{ width: 2, flex: 1, minHeight: 38, backgroundColor: colors.ink }} />
                  )}
                </View>
                <View style={{ marginLeft: space.md, flex: 1 }}>
                  <Text style={{ ...type.body, color: i === 0 ? colors.text : colors.textMuted }}>
                    {statusLabel(h.to_status)}
                  </Text>
                  <Text style={{ ...type.caption, color: colors.textMuted }}>{formatDateTime(h.created_at)}</Text>
                  {!!h.note && <Text style={{ ...type.caption, color: colors.textMuted }}>{h.note}</Text>}
                </View>
              </View>
            ))}
          </Card>
        )}

        {/* Cancel */}
        {order.can_cancel && (
          <Pressable
            onPress={confirmCancel}
            disabled={cancelling}
            style={{
              marginTop: space.sm,
              height: 48,
              borderRadius: radius.pill,
              borderWidth: 1.5,
              borderColor: colors.danger,
              alignItems: "center",
              justifyContent: "center",
              opacity: cancelling ? 0.5 : 1,
            }}
          >
            {cancelling ? (
              <ActivityIndicator color={colors.danger} />
            ) : (
              <Text style={{ ...type.heading, color: colors.danger }}>Order cancel karein</Text>
            )}
          </Pressable>
        )}
      </ScrollView>
    </View>
  );
}
