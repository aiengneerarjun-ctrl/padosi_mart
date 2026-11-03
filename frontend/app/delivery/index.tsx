import { useCallback, useRef, useState } from "react";
import { ActivityIndicator, Alert, Linking, Pressable, RefreshControl, ScrollView, Text, TextInput, View } from "react-native";
import { useFocusEffect, useRouter } from "expo-router";
import * as Location from "expo-location";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { ApiError, errorMessage } from "../../src/api/client";
import {
  acceptDelivery,
  AvailableDelivery,
  confirmDelivery,
  DeliveryCash,
  DeliveryEarnings,
  DeliveryPartner,
  DeliveryReviews,
  failDelivery,
  getAvailableDeliveries,
  getCurrentDelivery,
  getDeliveryCash,
  getDeliveryEarnings,
  getDeliveryPartner,
  getDeliveryReviews,
  goOffline,
  goOnline,
  MyDelivery,
  PickupStore,
  pickupStoreOrder,
  releaseDelivery,
  startDelivery,
} from "../../src/api/delivery";
import { useAuth } from "../../src/auth/AuthContext";
import { Button } from "../../src/components/Button";
import { Badge, Card, ErrorText, KV, SellerHeader } from "../../src/components/seller/ui";
import { colors, radius, space, type } from "../../src/theme";

const money = (value: number) => `₹${Number(value || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
const timestamp = (value: string) => new Date(value).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });

async function getCoords() {
  let permission = await Location.getForegroundPermissionsAsync();
  if (!permission.granted) permission = await Location.requestForegroundPermissionsAsync();
  if (!permission.granted) throw new Error("Nearby orders dekhne ke liye location permission zaroori hai.");
  const position = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
  return { lat: position.coords.latitude, lng: position.coords.longitude };
}

export default function DeliveryHome() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { signOut } = useAuth();
  const busyRefresh = useRef(false);
  const [partner, setPartner] = useState<DeliveryPartner | null>(null);
  const [current, setCurrent] = useState<MyDelivery[]>([]);
  const [available, setAvailable] = useState<AvailableDelivery[]>([]);
  const [earnings, setEarnings] = useState<DeliveryEarnings | null>(null);
  const [cash, setCash] = useState<DeliveryCash | null>(null);
  const [reviews, setReviews] = useState<DeliveryReviews | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [action, setAction] = useState("");
  const [error, setError] = useState("");
  const [otpByOrder, setOtpByOrder] = useState<Record<string, string>>({});
  const [failOrderId, setFailOrderId] = useState<string | null>(null);
  const [failCode, setFailCode] = useState("CUSTOMER_UNREACHABLE");
  const [failNote, setFailNote] = useState("");

  const refreshData = useCallback(async (showSpinner = true) => {
    if (busyRefresh.current) return;
    busyRefresh.current = true;
    if (showSpinner) setRefreshing(true);
    setError("");
    try {
      const profile = await getDeliveryPartner();
      setPartner(profile);
      if (profile.status !== "ACTIVE") {
          router.replace("/delivery/apply");
        return;
      }

      const active = await getCurrentDelivery();
      setCurrent(active);

      const [earned, collected, rated] = await Promise.allSettled([getDeliveryEarnings(), getDeliveryCash(), getDeliveryReviews()]);
      if (earned.status === "fulfilled") setEarnings(earned.value);
      if (collected.status === "fulfilled") setCash(collected.value);
      if (rated.status === "fulfilled") setReviews(rated.value);

      if (profile.is_online) {
        try {
          const coords = await getCoords();
          setAvailable(await getAvailableDeliveries(coords.lat, coords.lng));
        } catch (e) {
          setAvailable([]);
          setError(errorMessage(e));
        }
      } else {
        setAvailable([]);
      }
    } catch (e) {
      if (e instanceof ApiError && e.code === "NOT_A_PARTNER") {
        router.replace("/delivery/apply");
      } else {
        setError(errorMessage(e));
      }
    } finally {
      busyRefresh.current = false;
      setRefreshing(false);
    }
  }, [router]);

  useFocusEffect(
    useCallback(() => {
      void refreshData();
      const timer = setInterval(() => void refreshData(false), 30000);
      return () => clearInterval(timer);
    }, [refreshData]),
  );

  const perform = async (key: string, task: () => Promise<unknown>, success?: string) => {
    setAction(key);
    setError("");
    try {
      await task();
      if (success) Alert.alert("Ho gaya", success);
      await refreshData();
      return true;
    } catch (e) {
      setError(errorMessage(e));
      return false;
    } finally {
      setAction("");
    }
  };

  const toggleOnline = () => {
    if (!partner) return;
    void perform("online", async () => {
      const updated = partner.is_online ? await goOffline() : await goOnline();
      setPartner(updated);
    }, partner.is_online ? "Aap offline ho gaye." : "Aap online hain. Nearby orders check ho rahe hain.");
  };

  const accept = (order: AvailableDelivery) => {
    void perform(`accept-${order.order_id}`, async () => {
      const coords = await getCoords();
      await acceptDelivery(order.order_id, coords.lat, coords.lng);
    }, `${order.order_number} aapko assign ho gaya.`);
  };

  const openMap = (lat: number, lng: number) =>
    void Linking.openURL(`https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}`);

  const confirmOtp = (delivery: MyDelivery) => {
    const otp = otpByOrder[delivery.order_id] || "";
    if (otp.length !== 4) return;
    void (async () => {
      const completed = await perform(`deliver-${delivery.order_id}`, () => confirmDelivery(delivery.order_id, otp), "Order OTP se delivered confirm ho gaya.");
      if (completed) setOtpByOrder((values) => ({ ...values, [delivery.order_id]: "" }));
    })();
  };

  const submitFail = (delivery: MyDelivery) => {
    if (failCode === "OTHER" && !failNote.trim()) return;
    Alert.alert("Delivery fail karein?", "Order fail mark hoga aur shop ko return process karna hoga.", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Confirm",
        style: "destructive",
        onPress: () => void (async () => {
          const completed = await perform(`fail-${delivery.order_id}`, () => failDelivery(delivery.order_id, failCode, failNote), "Issue record ho gaya.");
          if (completed) setFailOrderId(null);
        })(),
      },
    ]);
  };

  const cashBlocked = !!cash?.limit_reached;

  return (
    <View style={{ flex: 1, backgroundColor: colors.canvas }}>
      <SellerHeader
        title="Delivery dashboard"
        subtitle={partner?.full_name || "Delivery partner"}
        right={<Pressable onPress={signOut} hitSlop={12}><Text style={{ ...type.body, color: colors.marigold }}>Logout</Text></Pressable>}
      />
      <ScrollView
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refreshData} tintColor={colors.ink} />}
        contentContainerStyle={{ padding: space.lg, paddingBottom: insets.bottom + space.xxl }}
      >
        <Card style={{ backgroundColor: partner?.is_online ? "#EAF5EE" : colors.surface }}>
          <View style={{ flexDirection: "row", alignItems: "center" }}>
            <View style={{ flex: 1 }}>
              <Text style={{ ...type.caption, color: colors.textMuted }}>Aapka status</Text>
              <Text style={{ ...type.title, color: colors.text, marginTop: 2 }}>{partner?.is_online ? "Online · Orders mil sakte hain" : "Offline · Orders nahi aayenge"}</Text>
            </View>
            <Pressable
              accessibilityRole="switch"
              accessibilityState={{ checked: !!partner?.is_online }}
              disabled={!partner || partner.status !== "ACTIVE" || !!current.length || !!action}
              onPress={toggleOnline}
              style={{ backgroundColor: partner?.is_online ? colors.success : colors.line, borderRadius: radius.pill, paddingHorizontal: space.lg, paddingVertical: space.sm }}
            >
              {action === "online" ? <ActivityIndicator color="#fff" /> : <Text style={{ ...type.heading, color: "#fff" }}>{partner?.is_online ? "Online" : "Go online"}</Text>}
            </Pressable>
          </View>
          {!!current.length && <Text style={{ ...type.caption, color: colors.textMuted, marginTop: space.sm }}>Chalta order poora hone ke baad hi offline ho sakte hain.</Text>}
          {cashBlocked && <Text style={{ ...type.caption, color: colors.danger, marginTop: space.sm }}>COD cash limit poori hai. Naya order lene se pehle jama cash admin se settle karein.</Text>}
        </Card>

        {!!error && <View style={{ marginTop: space.md }}><ErrorText>{error}</ErrorText></View>}

        {current.length > 0 && (
          <View style={{ marginTop: space.lg }}>
            <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: space.sm }}>
              <Text style={{ ...type.title, color: colors.text }}>Active deliveries</Text>
              <Badge label={`${current.length} active`} tone="progress" />
            </View>
            {current.map((delivery) => (
            <Card key={delivery.order_id} style={{ marginBottom: space.md, borderColor: colors.marigold, borderWidth: 1.5 }}>
            <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
              <Text style={{ ...type.title, color: colors.text }}>{delivery.order_number}</Text>
              <Badge label={statusLabel(delivery.status)} tone="progress" />
            </View>
            <Text style={{ ...type.caption, color: colors.textMuted, marginTop: space.xs }}>Order accept hua {timestamp(delivery.assigned_at)}</Text>
            <Text style={{ ...type.heading, color: colors.text, marginTop: space.lg }}>Pickup stops</Text>
            {delivery.stores.map((store) => (
              <StoreStop
                key={store.store_order_id}
                store={store}
                busy={action === `pickup-${delivery.order_id}-${store.store_order_id}`}
                onPickup={() => void perform(`pickup-${delivery.order_id}-${store.store_order_id}`, () => pickupStoreOrder(delivery.order_id, store.store_order_id))}
                onMap={() => openMap(store.latitude, store.longitude)}
              />
            ))}

            <View style={{ marginTop: space.lg }}>
              <Text style={{ ...type.heading, color: colors.text }}>Customer delivery</Text>
              <Text style={{ ...type.body, color: colors.text, marginTop: space.xs }}>{delivery.receiver_name}</Text>
              <Text style={{ ...type.body, color: colors.textMuted }}>{delivery.address_line}{delivery.landmark ? ` · ${delivery.landmark}` : ""}</Text>
              <View style={{ flexDirection: "row", marginTop: space.sm }}>
                <Pressable onPress={() => void Linking.openURL(`tel:${delivery.receiver_phone}`)} style={actionPill}>
                  <Ionicons name="call-outline" size={17} color={colors.ink} /><Text style={pillText}>  Customer ko call karein</Text>
                </Pressable>
                <Pressable onPress={() => openMap(delivery.latitude, delivery.longitude)} style={[actionPill, { marginLeft: space.sm }]}>
                  <Ionicons name="navigate-outline" size={17} color={colors.ink} /><Text style={pillText}>  Raasta</Text>
                </Pressable>
              </View>
              <KV k="Payment" v={delivery.payment_method === "COD" ? "Cash on delivery" : "Online paid"} />
              {delivery.amount_due > 0 && <KV k="Customer se cash lena hai" v={money(delivery.amount_due)} bold color={colors.danger} />}
            </View>

            {delivery.status === "PICKED_UP" && (
              <View style={{ marginTop: space.lg }}>
                <Button label="Customer ke liye nikal padein" onPress={() => void perform(`start-${delivery.order_id}`, () => startDelivery(delivery.order_id))} loading={action === `start-${delivery.order_id}`} />
              </View>
            )}

            {delivery.status === "OUT_FOR_DELIVERY" && (
              <View style={{ marginTop: space.lg, padding: space.md, borderRadius: radius.md, backgroundColor: "#FFF8E5" }}>
                <Text style={{ ...type.heading, color: colors.text }}>Customer ka 4 digit PIN</Text>
                <Text style={{ ...type.caption, color: colors.textMuted }}>Customer ke order screen par dikh raha PIN customer se lekar yahan daalein.</Text>
                <TextInput
                  value={otpByOrder[delivery.order_id] || ""}
                  onChangeText={(value) => setOtpByOrder((values) => ({ ...values, [delivery.order_id]: value.replace(/\D/g, "").slice(0, 4) }))}
                  keyboardType="number-pad"
                  maxLength={4}
                  placeholder="• • • •"
                  style={{ ...type.title, textAlign: "center", color: colors.text, letterSpacing: 12, marginTop: space.sm, backgroundColor: colors.surface, borderRadius: radius.md, padding: space.md }}
                />
                <View style={{ marginTop: space.sm }}><Button label="PIN se delivery confirm karein" onPress={() => confirmOtp(delivery)} loading={action === `deliver-${delivery.order_id}`} disabled={(otpByOrder[delivery.order_id] || "").length !== 4} /></View>
              </View>
            )}

            {delivery.status === "ASSIGNED" && !delivery.stores.some((s) => s.status === "PICKED_UP") && (
              <View style={{ marginTop: space.sm }}>
                <Button
                  label="Order chhod dein"
                  variant="ghost"
                  onPress={() => Alert.alert("Order chhod dein?", "Ye order doosre nearby delivery partners ko dikhega.", [
                    { text: "Nahi", style: "cancel" },
                    { text: "Haan, chhod dein", style: "destructive", onPress: () => void perform(`release-${delivery.order_id}`, () => releaseDelivery(delivery.order_id)) },
                  ])}
                />
              </View>
            )}

            {delivery.status === "OUT_FOR_DELIVERY" && (
              <View style={{ marginTop: space.md }}>
                <Button label={failOrderId === delivery.order_id ? "Issue form band karein" : "Delivery me dikkat?"} variant="ghost" onPress={() => setFailOrderId((v) => v === delivery.order_id ? null : delivery.order_id)} />
                {failOrderId === delivery.order_id && <FailDeliveryForm code={failCode} setCode={setFailCode} note={failNote} setNote={setFailNote} onSubmit={() => submitFail(delivery)} busy={action === `fail-${delivery.order_id}`} />}
              </View>
            )}
          </Card>
            ))}
          </View>
        )}
          <View style={{ marginTop: space.lg }}>
            <Text style={{ ...type.title, color: colors.text, marginBottom: space.sm }}>Nearby orders</Text>
            {partner?.is_online ? (
              available.length ? available.map((order) => (
                <AvailableCard
                  key={order.order_id}
                  order={order}
                  busy={action === `accept-${order.order_id}`}
                  disabled={cashBlocked || !partner.is_online || !!action}
                  onAccept={() => accept(order)}
                  onMap={(store) => openMap(store.latitude, store.longitude)}
                />
              )) : <Card><Text style={{ ...type.heading, color: colors.text }}>Abhi nearby order nahi hai</Text><Text style={{ ...type.caption, color: colors.textMuted, marginTop: space.xs }}>Online rahen. Naye orders yahan automatically check hote rahenge.</Text></Card>
            ) : (
              <Card><Text style={{ ...type.heading, color: colors.text }}>Orders dekhne ke liye online ho jaiye</Text><Text style={{ ...type.caption, color: colors.textMuted, marginTop: space.xs }}>Online hone par aapke aas-paas ke available orders yahan aayenge.</Text></Card>
            )}
          </View>

        <Text style={{ ...type.title, color: colors.text, marginTop: space.xl, marginBottom: space.sm }}>Kamai aur COD hisaab</Text>
        <View style={{ flexDirection: "row" }}>
          <Metric title="Kul kamai" value={money(earnings?.total_earned ?? 0)} />
          <Metric title="Aapko dena baaki" value={money(earnings?.due ?? 0)} accent />
        </View>
        <View style={{ flexDirection: "row", marginTop: space.sm }}>
          <Metric title="COD cash haath me" value={money(cash?.cash_in_hand ?? 0)} accent={cashBlocked} />
          <Metric title="Cash limit" value={money(cash?.cash_limit ?? 0)} />
        </View>
        {cash && <Text style={{ ...type.caption, color: colors.textMuted, marginTop: space.xs }}>Jama: {money(cash.cash_deposited)} · COD collect kiya: {money(cash.cash_collected)}</Text>}

        {earnings?.recent_earnings.length ? (
          <Card style={{ marginTop: space.md }}>
            <Text style={{ ...type.heading, color: colors.text, marginBottom: space.xs }}>Recent deliveries</Text>
            {earnings.recent_earnings.slice(0, 5).map((row) => <KV key={row.order_id} k={`${row.order_number} · ${timestamp(row.delivered_at)}`} v={money(row.amount)} />)}
          </Card>
        ) : null}
        {cash?.recent_collections.length ? (
          <Card style={{ marginTop: space.md }}>
            <Text style={{ ...type.heading, color: colors.text, marginBottom: space.xs }}>Recent COD collections</Text>
            {cash.recent_collections.slice(0, 5).map((row) => <KV key={row.order_id} k={`${row.order_number} · ${timestamp(row.delivered_at)}`} v={money(row.amount)} />)}
          </Card>
        ) : null}
        {cash?.recent_deposits.length ? (
          <Card style={{ marginTop: space.md }}>
            <Text style={{ ...type.heading, color: colors.text, marginBottom: space.xs }}>Recent cash deposits</Text>
            {cash.recent_deposits.slice(0, 5).map((row) => <KV key={row.id} k={`${timestamp(row.created_at)}${row.note ? ` · ${row.note}` : ""}`} v={money(row.amount)} />)}
          </Card>
        ) : null}
        {reviews && (
          <Card style={{ marginTop: space.md }}>
            <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
              <Text style={{ ...type.heading, color: colors.text }}>Customer rating</Text>
              <Text style={{ ...type.heading, color: colors.ink }}>
                {reviews.summary.average == null ? "Naya" : `★ ${reviews.summary.average.toFixed(1)}`}
                <Text style={{ ...type.caption, color: colors.textMuted }}> · {reviews.summary.count} reviews</Text>
              </Text>
            </View>
            {reviews.reviews.slice(0, 3).map((review, index) => (
              <View key={`${review.order_number}-${index}`} style={{ borderTopWidth: index ? 1 : 0, borderColor: colors.line, marginTop: space.sm, paddingTop: space.sm }}>
                <Text style={{ ...type.caption, color: colors.marigoldDeep }}>{"★".repeat(review.rating)}{"☆".repeat(5 - review.rating)} · {review.order_number}</Text>
                {!!review.comment && <Text style={{ ...type.body, color: colors.text, marginTop: 2 }}>{review.comment}</Text>}
              </View>
            ))}
            {!reviews.reviews.length && <Text style={{ ...type.caption, color: colors.textMuted, marginTop: space.xs }}>Delivery ke baad customer aapko rating de sakte hain.</Text>}
          </Card>
        )}
        {earnings?.recent_payouts.length ? (
          <Card style={{ marginTop: space.md }}>
            <Text style={{ ...type.heading, color: colors.text, marginBottom: space.xs }}>Recent payouts</Text>
            {earnings.recent_payouts.slice(0, 5).map((row) => <KV key={row.id} k={`${timestamp(row.created_at)}${row.note ? ` · ${row.note}` : ""}`} v={money(row.amount)} />)}
          </Card>
        ) : null}
      </ScrollView>
    </View>
  );
}

const actionPill = { flexDirection: "row" as const, alignItems: "center" as const, backgroundColor: "#E4F0EE", paddingHorizontal: space.md, paddingVertical: space.sm, borderRadius: radius.pill };
const pillText = { ...type.caption, color: colors.ink };

function statusLabel(status: string) {
  if (status === "ASSIGNED") return "Pickup baaki";
  if (status === "PICKED_UP") return "Saman uth gaya";
  return "Customer ke raaste me";
}

function StoreStop({ store, busy, onPickup, onMap }: { store: PickupStore; busy: boolean; onPickup: () => void; onMap: () => void }) {
  const picked = store.status === "PICKED_UP";
  const ready = store.status === "READY_FOR_PICKUP";
  return (
    <View style={{ borderTopWidth: 1, borderColor: colors.line, paddingTop: space.md, marginTop: space.md }}>
      <View style={{ flexDirection: "row", alignItems: "center" }}>
        <Text style={{ ...type.heading, color: colors.text, flex: 1 }}>{store.store_name}</Text>
        <Badge label={picked ? "Uthaya" : ready ? "Taiyar" : "Taiyar ho raha"} tone={picked ? "good" : ready ? "progress" : "neutral"} />
      </View>
      <Text style={{ ...type.caption, color: colors.textMuted, marginTop: 2 }}>{store.store_address}</Text>
      {store.items.map((item, index) => <Text key={`${item.name}-${index}`} style={{ ...type.caption, color: colors.text, marginTop: 3 }}>• {item.quantity} × {item.name} ({item.selling_unit})</Text>)}
      {!picked && (
        <View style={{ marginTop: space.sm }}>
          <Button label={ready ? "Is dukaan se pickup confirm karein" : "Dukaan ke ready karne ka intezaar"} onPress={ready ? onPickup : () => undefined} loading={busy} disabled={!ready} variant={ready ? "primary" : "ghost"} />
          {!ready && <Pressable onPress={onMap} style={{ alignSelf: "center", padding: space.sm }}><Text style={{ ...type.caption, color: colors.ink }}>Map me dukaan dekhein</Text></Pressable>}
        </View>
      )}
    </View>
  );
}

function AvailableCard({ order, busy, disabled, onAccept, onMap }: { order: AvailableDelivery; busy: boolean; disabled: boolean; onAccept: () => void; onMap: (store: PickupStore) => void }) {
  return (
    <Card style={{ marginBottom: space.md }}>
      <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
        <Text style={{ ...type.title, color: colors.text }}>{order.order_number}</Text>
        <Badge label={order.payment_method === "COD" ? "COD" : "Online paid"} tone={order.payment_method === "COD" ? "progress" : "good"} />
      </View>
      <KV k="Pickup distance" v={order.pickup_distance_km == null ? "—" : `${order.pickup_distance_km} km`} bold />
      <KV k="Delivery distance" v={`${order.drop_distance_km} km`} />
      <KV k="Delivery fee" v={money(order.delivery_fee)} />
      {order.amount_due > 0 && <KV k="Customer se collect karein" v={money(order.amount_due)} color={colors.danger} />}
      {order.stores.map((store) => (
        <Pressable key={store.store_order_id} onPress={() => onMap(store)} style={{ borderTopWidth: 1, borderColor: colors.line, marginTop: space.sm, paddingTop: space.sm }}>
          <Text style={{ ...type.heading, color: colors.text }}>{store.store_name} <Text style={{ color: colors.ink }}>· map</Text></Text>
          <Text style={{ ...type.caption, color: colors.textMuted }}>{store.store_address}</Text>
          <Text style={{ ...type.caption, color: colors.text, marginTop: 2 }}>{store.items.map((item) => `${item.quantity} × ${item.name}`).join("  ·  ")}</Text>
        </Pressable>
      ))}
      <View style={{ marginTop: space.md }}><Button label="Order accept karein" onPress={onAccept} loading={busy} disabled={disabled} /></View>
    </Card>
  );
}

function Metric({ title, value, accent = false }: { title: string; value: string; accent?: boolean }) {
  return (
    <View style={{ flex: 1, marginRight: space.sm, backgroundColor: accent ? "#FFF1CB" : colors.surface, borderRadius: radius.md, borderWidth: 1, borderColor: colors.line, padding: space.md }}>
      <Text style={{ ...type.caption, color: colors.textMuted }}>{title}</Text>
      <Text style={{ ...type.title, color: colors.text, marginTop: 2 }}>{value}</Text>
    </View>
  );
}

const FAILURE_REASONS = [
  ["CUSTOMER_UNREACHABLE", "Customer se sampark nahi ho paya"],
  ["CUSTOMER_REFUSED", "Customer ne order mana kiya"],
  ["WRONG_ADDRESS", "Pata galat hai"],
  ["PARTNER_ISSUE", "Delivery partner ki dikkat"],
  ["OTHER", "Kuch aur wajah"],
];

function FailDeliveryForm({ code, setCode, note, setNote, onSubmit, busy }: { code: string; setCode: (v: string) => void; note: string; setNote: (v: string) => void; onSubmit: () => void; busy: boolean }) {
  return (
    <View style={{ backgroundColor: colors.surface, borderRadius: radius.md, padding: space.md, marginTop: space.sm }}>
      <Text style={{ ...type.heading, color: colors.text }}>Dikkat ka karan</Text>
      {FAILURE_REASONS.map(([value, label]) => (
        <Pressable key={value} onPress={() => setCode(value)} style={{ flexDirection: "row", alignItems: "center", paddingVertical: space.xs }}>
          <Ionicons name={code === value ? "radio-button-on" : "radio-button-off"} size={19} color={code === value ? colors.ink : colors.textMuted} />
          <Text style={{ ...type.caption, color: colors.text, marginLeft: space.sm }}>{label}</Text>
        </Pressable>
      ))}
      {code === "OTHER" && <TextInput value={note} onChangeText={setNote} placeholder="Kya hua?" maxLength={250} style={{ ...type.body, backgroundColor: colors.canvas, borderRadius: radius.sm, padding: space.md, color: colors.text }} />}
      <View style={{ marginTop: space.md }}><Button label="Delivery fail report karein" onPress={onSubmit} loading={busy} disabled={code === "OTHER" && !note.trim()} /></View>
    </View>
  );
}
