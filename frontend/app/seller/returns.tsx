import { useCallback, useState } from "react";
import { FlatList, RefreshControl, Switch, Text, View } from "react-native";
import { useFocusEffect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { errorMessage } from "../../src/api/client";
import { listReturns, receiveReturn, ReturnOut } from "../../src/api/sellerMoney";
import { Button } from "../../src/components/Button";
import { Badge, Card, Chips, EmptyState, ErrorText, Field, SellerHeader, Sheet, Spinner } from "../../src/components/seller/ui";
import { formatDateTime } from "../../src/lib/orderUi";
import { colors, space, type } from "../../src/theme";

type Tab = "PENDING" | "RECEIVED";

export default function SellerReturns() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [tab, setTab] = useState<Tab>("PENDING");
  const [rows, setRows] = useState<ReturnOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const [target, setTarget] = useState<ReturnOut | null>(null);
  const [stockOk, setStockOk] = useState(true);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [sheetError, setSheetError] = useState("");

  const load = useCallback(async (t: Tab) => {
    setError("");
    try {
      setRows(await listReturns(t));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load(tab);
    }, [load, tab]),
  );

  const pickTab = (t: Tab) => {
    setLoading(true);
    setTab(t);
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await load(tab);
    setRefreshing(false);
  };

  const openReceive = (r: ReturnOut) => {
    setTarget(r);
    setStockOk(true);
    setNote("");
    setSheetError("");
  };

  const confirm = async () => {
    if (!target) return;
    setBusy(true);
    setSheetError("");
    try {
      await receiveReturn(target.store_order_id, stockOk, note.trim());
      setTarget(null);
      await load(tab);
    } catch (e) {
      setSheetError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.canvas }}>
      <SellerHeader title="Returns" subtitle="Delivery nahi hui to saman wapas aata hai" onBack={() => (router.canGoBack() ? router.back() : router.replace("/seller"))} />
      <View style={{ paddingVertical: space.md }}>
        <Chips
          value={tab}
          onChange={pickTab}
          options={[
            { value: "PENDING" as Tab, label: "Wapas aana baaki" },
            { value: "RECEIVED" as Tab, label: "Mil gaya" },
          ]}
        />
      </View>
      {loading ? (
        <Spinner />
      ) : (
        <FlatList
          data={rows}
          keyExtractor={(r) => r.store_order_id}
          contentContainerStyle={{ padding: space.lg, paddingTop: 0, paddingBottom: insets.bottom + space.xxl }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.ink} />}
          ListHeaderComponent={<ErrorText>{error}</ErrorText>}
          ListEmptyComponent={
            error ? null : (
              <EmptyState
                title={tab === "PENDING" ? "Koi saman wapas aana baaki nahi" : "Abhi koi return nahi mila"}
                body={tab === "PENDING" ? "Jab kisi order ki delivery nahi ho paati, saman yahan dikhta hai." : undefined}
              />
            )
          }
          renderItem={({ item: r }) => (
            <Card style={{ marginBottom: space.sm }}>
              <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
                <Text style={{ ...type.heading, color: colors.text }}>#{r.order_number}</Text>
                <Badge label={r.status === "PENDING" ? "Wapas aana baaki" : r.restocked ? "Mil gaya, stock jura" : "Mil gaya"} tone={r.status === "PENDING" ? "progress" : "good"} />
              </View>
              <Text style={{ ...type.caption, color: colors.textMuted }}>
                {r.was_picked_up ? "Partner saman le gaya tha, delivery nahi ho payi" : "Partner utha nahi paya"}
                {r.fail_reason ? ` · ${r.fail_reason}` : ""}
              </Text>
              <View style={{ marginTop: space.sm }}>
                {r.items.map((it, i) => (
                  <Text key={i} style={{ ...type.body, color: colors.text }}>
                    {it.name} ({it.selling_unit}) × {it.quantity}
                  </Text>
                ))}
              </View>
              {r.status === "RECEIVED" && (
                <Text style={{ ...type.caption, color: colors.textMuted, marginTop: space.sm }}>
                  {r.received_at ? formatDateTime(r.received_at) : ""}
                  {r.note ? ` · ${r.note}` : ""}
                </Text>
              )}
              {r.status === "PENDING" && (
                <View style={{ marginTop: space.md }}>
                  <Button label="Saman wapas mil gaya" onPress={() => openReceive(r)} />
                </View>
              )}
            </Card>
          )}
        />
      )}

      <Sheet visible={!!target} onClose={() => setTarget(null)} title="Saman wapas mila">
        {target && (
          <>
            <Text style={{ ...type.body, color: colors.textMuted }}>Order #{target.order_number}</Text>
            <View style={{ flexDirection: "row", alignItems: "center", marginTop: space.lg }}>
              <View style={{ flex: 1 }}>
                <Text style={{ ...type.heading, color: colors.text }}>Saman theek hai, phir bech sakte hain</Text>
                <Text style={{ ...type.caption, color: colors.textMuted }}>
                  Haan rakhne par stock wapas jud jayega. Kharab ho to band kar dein.
                </Text>
              </View>
              <Switch value={stockOk} onValueChange={setStockOk} trackColor={{ false: colors.line, true: colors.success }} />
            </View>
            <Field label="Note (zaroori nahi)" value={note} onChangeText={setNote} maxLength={300} placeholder="Jaise 2 packet phat gaye the" />
            <ErrorText>{sheetError}</ErrorText>
            <View style={{ marginTop: space.xl }}>
              <Button label="Pakka karein" onPress={confirm} loading={busy} />
            </View>
          </>
        )}
      </Sheet>
    </View>
  );
}
