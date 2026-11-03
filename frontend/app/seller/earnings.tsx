import { useCallback, useState } from "react";
import { RefreshControl, ScrollView, Text, View } from "react-native";
import { useFocusEffect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { errorMessage } from "../../src/api/client";
import { EarningsSummary, getEarnings } from "../../src/api/sellerMoney";
import { Button } from "../../src/components/Button";
import { Card, EmptyState, KV, SellerHeader, Spinner } from "../../src/components/seller/ui";
import { formatPrice } from "../../src/lib/media";
import { formatDateTime } from "../../src/lib/orderUi";
import { colors, radius, space, type } from "../../src/theme";

export default function SellerEarnings() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [data, setData] = useState<EarningsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      setData(await getEarnings());
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

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

  return (
    <View style={{ flex: 1, backgroundColor: colors.canvas }}>
      <SellerHeader title="Kamai" subtitle="Deliver hue orders ka hisaab" onBack={() => (router.canGoBack() ? router.back() : router.replace("/seller"))} />
      {loading ? (
        <Spinner />
      ) : !data ? (
        <EmptyState title={error || "Hisaab nahi aa paya"} action={<Button label="Dobara try karein" onPress={load} variant="ghost" />} />
      ) : (
        <ScrollView
          contentContainerStyle={{ padding: space.lg, paddingBottom: insets.bottom + space.xxl }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.ink} />}
        >
          {/* Sabse zaroori: abhi kitna milna baaki hai */}
          <View style={{ backgroundColor: colors.ink, borderRadius: radius.lg, padding: space.xl }}>
            <Text style={{ ...type.body, color: "#B9D3CF" }}>Padosi se abhi milna baaki</Text>
            <Text style={{ ...type.display, fontSize: 40, lineHeight: 46, color: colors.onInk }}>{formatPrice(data.due)}</Text>
            <Text style={{ ...type.caption, color: "#B9D3CF", marginTop: space.xs }}>
              Ye paisa admin aapko deta hai. Mil jane par neeche “Mila hua paisa” me dikhega.
            </Text>
          </View>

          <Card style={{ marginTop: space.lg }}>
            <KV k="Kul bikri" v={formatPrice(data.total_sales)} />
            <KV k="Padosi ka commission" v={`− ${formatPrice(data.total_commission)}`} color={colors.danger} />
            {data.total_seller_discount > 0 && (
              <KV k="Aapke coupon ka discount" v={`− ${formatPrice(data.total_seller_discount)}`} color={colors.danger} />
            )}
            <View style={{ height: 1, backgroundColor: colors.line, marginVertical: space.sm }} />
            <KV k="Aapki kamai" v={formatPrice(data.total_earned)} bold />
            <KV k="Mila hua paisa" v={formatPrice(data.total_paid)} color={colors.success} />
            <KV k="Baaki" v={formatPrice(data.due)} bold />
          </Card>

          <Text style={{ ...type.heading, color: colors.text, marginTop: space.xl, marginBottom: space.sm }}>Haal ke orders</Text>
          {data.recent_orders.length === 0 ? (
            <Card>
              <Text style={{ ...type.body, color: colors.textMuted }}>
                Abhi koi order deliver nahi hua. Delivery ke baad yahan hisaab dikhega.
              </Text>
            </Card>
          ) : (
            <Card style={{ padding: 0 }}>
              {data.recent_orders.map((o, i) => (
                <View
                  key={o.order_id}
                  style={{ padding: space.lg, borderTopWidth: i === 0 ? 0 : 1, borderTopColor: colors.line }}
                >
                  <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
                    <Text style={{ ...type.heading, color: colors.text }}>#{o.order_number}</Text>
                    <Text style={{ ...type.heading, color: colors.success }}>{formatPrice(o.net)}</Text>
                  </View>
                  <Text style={{ ...type.caption, color: colors.textMuted }}>
                    {formatDateTime(o.delivered_at)} · bikri {formatPrice(o.items_subtotal)} · commission {formatPrice(o.commission_amount)}
                    {o.seller_discount > 0 ? ` · coupon ${formatPrice(o.seller_discount)}` : ""}
                  </Text>
                  {o.commission_items.map((item, idx) => (
                    <Text key={`${item.name}-${idx}`} style={{ ...type.caption, color: colors.textMuted, marginTop: 3 }}>
                      {item.name} · {item.quantity} {item.selling_unit} · commission {formatPrice(item.commission_amount)} ({item.commission_mode === "FIXED" ? `₹${item.commission_value} × ${item.commission_unit_quantity} ${item.commission_unit}` : `${item.commission_value}%`})
                    </Text>
                  ))}
                </View>
              ))}
            </Card>
          )}

          <Text style={{ ...type.heading, color: colors.text, marginTop: space.xl, marginBottom: space.sm }}>Mila hua paisa</Text>
          {data.recent_payouts.length === 0 ? (
            <Card>
              <Text style={{ ...type.body, color: colors.textMuted }}>Admin ne abhi tak koi payment nahi ki.</Text>
            </Card>
          ) : (
            <Card style={{ padding: 0 }}>
              {data.recent_payouts.map((p, i) => (
                <View
                  key={p.id}
                  style={{
                    flexDirection: "row",
                    padding: space.lg,
                    borderTopWidth: i === 0 ? 0 : 1,
                    borderTopColor: colors.line,
                  }}
                >
                  <View style={{ flex: 1 }}>
                    <Text style={{ ...type.body, color: colors.text }}>{p.amount < 0 ? "Sudhaar" : "Payment mila"}</Text>
                    <Text style={{ ...type.caption, color: colors.textMuted }}>
                      {formatDateTime(p.created_at)}
                      {p.note ? ` · ${p.note}` : ""}
                    </Text>
                  </View>
                  <Text style={{ ...type.heading, color: p.amount < 0 ? colors.danger : colors.success }}>
                    {p.amount < 0 ? "− " : ""}
                    {formatPrice(Math.abs(p.amount))}
                  </Text>
                </View>
              ))}
            </Card>
          )}
        </ScrollView>
      )}
    </View>
  );
}
