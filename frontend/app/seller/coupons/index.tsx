import { useCallback, useState } from "react";
import { FlatList, Pressable, RefreshControl, Switch, Text, View } from "react-native";
import { useFocusEffect, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { errorMessage } from "../../../src/api/client";
import { listCoupons, SellerCoupon, setCouponActive } from "../../../src/api/sellerMoney";
import { Button } from "../../../src/components/Button";
import { Badge, Card, EmptyState, ErrorText, SellerHeader, Spinner } from "../../../src/components/seller/ui";
import { formatPrice } from "../../../src/lib/media";
import { colors, radius, space, type } from "../../../src/theme";

export function discountText(c: Pick<SellerCoupon, "discount_type" | "value" | "max_discount">): string {
  if (c.discount_type === "FLAT") return `${formatPrice(c.value)} chhoot`;
  if (c.discount_type === "PERCENT") {
    return `${c.value}% chhoot${c.max_discount ? ` (zyada se zyada ${formatPrice(c.max_discount)})` : ""}`;
  }
  return "Free delivery";
}

const dateOnly = (iso: string) => new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });

export default function SellerCoupons() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [rows, setRows] = useState<SellerCoupon[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      setRows(await listCoupons());
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

  const toggle = async (c: SellerCoupon, on: boolean) => {
    setBusyId(c.id);
    setError("");
    try {
      const updated = await setCouponActive(c.id, on);
      setRows((prev) => prev.map((x) => (x.id === c.id ? updated : x)));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusyId("");
    }
  };

  const now = Date.now();

  return (
    <View style={{ flex: 1, backgroundColor: colors.canvas }}>
      <SellerHeader
        title="Coupons"
        subtitle="Discount aapke payout se katta hai"
        onBack={() => (router.canGoBack() ? router.back() : router.replace("/seller"))}
        right={
          <Pressable
            onPress={() => router.push("/seller/coupons/new")}
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
      {loading ? (
        <Spinner />
      ) : (
        <FlatList
          data={rows}
          keyExtractor={(c) => c.id}
          contentContainerStyle={{ padding: space.lg, paddingBottom: insets.bottom + space.xxl }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.ink} />}
          ListHeaderComponent={<ErrorText>{error}</ErrorText>}
          ListEmptyComponent={
            error ? null : (
              <EmptyState
                title="Abhi koi coupon nahi"
                body="Coupon se naye customer aate hain aur purane wapas aate hain. Discount sirf aapke saman par lagta hai."
                action={<Button label="Pehla coupon banayein" onPress={() => router.push("/seller/coupons/new")} />}
              />
            )
          }
          renderItem={({ item: c }) => {
            const expired = new Date(c.expires_at).getTime() < now;
            const tone = !c.is_active ? "neutral" : expired ? "bad" : "good";
            const label = !c.is_active ? "Band" : expired ? "Khatam" : "Chalu";
            return (
              <Card style={{ marginBottom: space.sm }}>
                <View style={{ flexDirection: "row", alignItems: "center" }}>
                  <View style={{ flex: 1 }}>
                    <Text style={{ ...type.title, color: colors.ink, letterSpacing: 1 }}>{c.code}</Text>
                    <Text style={{ ...type.body, color: colors.text }}>{c.title}</Text>
                  </View>
                  <Switch
                    value={c.is_active}
                    disabled={busyId === c.id}
                    onValueChange={(v) => toggle(c, v)}
                    trackColor={{ false: colors.line, true: colors.success }}
                  />
                </View>
                <Text style={{ ...type.body, color: colors.text, marginTop: space.sm }}>{discountText(c)}</Text>
                <Text style={{ ...type.caption, color: colors.textMuted }}>
                  {c.min_order_amount > 0 ? `${formatPrice(c.min_order_amount)} ke order par · ` : ""}
                  {c.first_order_only ? "Sirf pehle order par · " : ""}
                  {dateOnly(c.expires_at)} tak
                </Text>
                <View style={{ flexDirection: "row", alignItems: "center", marginTop: space.sm }}>
                  <Badge label={label} tone={tone} />
                  <Text style={{ ...type.caption, color: colors.textMuted, marginLeft: space.sm, flex: 1 }}>
                    {c.used_count}
                    {c.total_limit ? `/${c.total_limit}` : ""} baar laga · {formatPrice(c.total_discount_given)} chhoot di
                  </Text>
                </View>
              </Card>
            );
          }}
        />
      )}
    </View>
  );
}
