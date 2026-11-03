import { useCallback, useState } from "react";
import { FlatList, RefreshControl, Text, View } from "react-native";
import { useFocusEffect, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { errorMessage } from "../../src/api/client";
import { getSellerReviews, SellerReviews } from "../../src/api/sellerMoney";
import { Card, Chips, EmptyState, ErrorText, SellerHeader, Spinner } from "../../src/components/seller/ui";
import { formatDateTime } from "../../src/lib/orderUi";
import { colors, radius, space, type } from "../../src/theme";

type Filter = "ALL" | "LOW";

function Stars({ n, size = 16 }: { n: number; size?: number }) {
  return (
    <View style={{ flexDirection: "row" }}>
      {[1, 2, 3, 4, 5].map((i) => (
        <Ionicons key={i} name={i <= n ? "star" : "star-outline"} size={size} color={colors.marigold} />
      ))}
    </View>
  );
}

export default function SellerReviewsScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [filter, setFilter] = useState<Filter>("ALL");
  const [data, setData] = useState<SellerReviews | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async (f: Filter) => {
    setError("");
    try {
      setData(await getSellerReviews(f === "LOW" ? 2 : undefined));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load(filter);
    }, [load, filter]),
  );

  const pick = (f: Filter) => {
    setLoading(true);
    setFilter(f);
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await load(filter);
    setRefreshing(false);
  };

  const summary = data?.summary;
  const total = summary?.count ?? 0;

  return (
    <View style={{ flex: 1, backgroundColor: colors.canvas }}>
      <SellerHeader title="Reviews" subtitle="Customer ne kya kaha" onBack={() => (router.canGoBack() ? router.back() : router.replace("/seller"))} />
      <View style={{ paddingVertical: space.md }}>
        <Chips
          value={filter}
          onChange={pick}
          options={[
            { value: "ALL" as Filter, label: "Sab" },
            { value: "LOW" as Filter, label: "2 star ya kam" },
          ]}
        />
      </View>
      {loading ? (
        <Spinner />
      ) : (
        <FlatList
          data={data?.reviews ?? []}
          keyExtractor={(r) => r.id}
          contentContainerStyle={{ padding: space.lg, paddingTop: 0, paddingBottom: insets.bottom + space.xxl }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.ink} />}
          ListHeaderComponent={
            <View>
              <ErrorText>{error}</ErrorText>
              {summary && (
                <Card style={{ marginBottom: space.md }}>
                  <View style={{ flexDirection: "row", alignItems: "center" }}>
                    <View style={{ alignItems: "center", marginRight: space.xl }}>
                      <Text style={{ ...type.display, fontSize: 38, lineHeight: 44, color: colors.text }}>
                        {summary.average != null ? summary.average.toFixed(1) : "–"}
                      </Text>
                      <Stars n={Math.round(summary.average ?? 0)} />
                      <Text style={{ ...type.caption, color: colors.textMuted, marginTop: 2 }}>{summary.count} review</Text>
                    </View>
                    <View style={{ flex: 1 }}>
                      {[5, 4, 3, 2, 1].map((s) => {
                        const c = summary.stars?.[String(s)] ?? 0;
                        return (
                          <View key={s} style={{ flexDirection: "row", alignItems: "center", marginVertical: 2 }}>
                            <Text style={{ ...type.caption, color: colors.textMuted, width: 14 }}>{s}</Text>
                            <View style={{ flex: 1, height: 6, borderRadius: 3, backgroundColor: colors.line, marginHorizontal: 6 }}>
                              <View
                                style={{
                                  width: total ? `${Math.round((c / total) * 100)}%` : "0%",
                                  height: 6,
                                  borderRadius: 3,
                                  backgroundColor: colors.marigold,
                                }}
                              />
                            </View>
                            <Text style={{ ...type.caption, color: colors.textMuted, width: 24, textAlign: "right" }}>{c}</Text>
                          </View>
                        );
                      })}
                    </View>
                  </View>
                </Card>
              )}
            </View>
          }
          ListEmptyComponent={
            error ? null : (
              <EmptyState
                title={filter === "LOW" ? "Koi kam rating wala review nahi" : "Abhi koi review nahi aaya"}
                body={filter === "ALL" ? "Order deliver hone ke baad customer review de sakte hain." : undefined}
              />
            )
          }
          renderItem={({ item: r }) => (
            <View
              style={{
                backgroundColor: colors.surface,
                borderWidth: 1,
                borderColor: colors.line,
                borderRadius: radius.md,
                padding: space.lg,
                marginBottom: space.sm,
              }}
            >
              <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
                <Stars n={r.rating} />
                <Text style={{ ...type.caption, color: colors.textMuted }}>{formatDateTime(r.created_at)}</Text>
              </View>
              {!!r.comment && <Text style={{ ...type.body, color: colors.text, marginTop: space.sm }}>{r.comment}</Text>}
              <Text style={{ ...type.caption, color: colors.textMuted, marginTop: space.sm }}>
                {r.reviewer_name} · order #{r.order_number}
              </Text>
            </View>
          )}
        />
      )}
    </View>
  );
}
