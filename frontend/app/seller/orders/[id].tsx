import { useCallback, useEffect, useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { errorMessage } from "../../../src/api/client";
import {
  acceptOrder,
  getSellerOrder,
  markUnavailable,
  preparingOrder,
  readyOrder,
  RemovalReason,
  rejectOrder,
  SellerOrder,
  SellerOrderItem,
} from "../../../src/api/sellerOrders";
import { Button } from "../../../src/components/Button";
import {
  Badge,
  Card,
  Chips,
  EmptyState,
  ErrorText,
  Field,
  KV,
  SellerHeader,
  Sheet,
  Spinner,
} from "../../../src/components/seller/ui";
import { formatPrice } from "../../../src/lib/media";
import { formatDateTime } from "../../../src/lib/orderUi";
import { paymentLabel, REMOVAL_REASONS, STORE_ORDER_STATUS } from "../../../src/seller/orderUi";
import { colors, radius, space, type } from "../../../src/theme";

export default function SellerOrderDetail() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { id } = useLocalSearchParams<{ id: string }>();

  const [order, setOrder] = useState<SellerOrder | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [busy, setBusy] = useState<"" | "accept" | "preparing" | "ready">("");
  const [error, setError] = useState("");

  // "Saman nahi hai" sheet
  const [item, setItem] = useState<SellerOrderItem | null>(null);
  const [itemReason, setItemReason] = useState<RemovalReason>("OUT_OF_STOCK");
  const [keepQty, setKeepQty] = useState(0);
  const [itemNote, setItemNote] = useState("");
  const [itemBusy, setItemBusy] = useState(false);
  const [itemError, setItemError] = useState("");

  // Poora order mana karne wali sheet
  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectCode, setRejectCode] = useState<RemovalReason>("OUT_OF_STOCK");
  const [rejectText, setRejectText] = useState("Saman abhi dukaan me nahi hai");
  const [rejectBusy, setRejectBusy] = useState(false);
  const [rejectError, setRejectError] = useState("");

  const load = useCallback(async () => {
    setLoadError("");
    try {
      setOrder(await getSellerOrder(id));
    } catch (e) {
      setLoadError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const step = async (kind: "accept" | "preparing" | "ready") => {
    if (!order) return;
    setBusy(kind);
    setError("");
    try {
      const fn = kind === "accept" ? acceptOrder : kind === "preparing" ? preparingOrder : readyOrder;
      setOrder(await fn(order.id));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy("");
    }
  };

  const openItem = (it: SellerOrderItem) => {
    setItem(it);
    setItemReason("OUT_OF_STOCK");
    setKeepQty(0);
    setItemNote("");
    setItemError("");
  };

  const submitItem = async () => {
    if (!order || !item) return;
    setItemBusy(true);
    setItemError("");
    try {
      setOrder(
        await markUnavailable(order.id, [
          { item_id: item.id, reason: itemReason, note: itemNote.trim() || null, available_quantity: keepQty },
        ]),
      );
      setItem(null);
    } catch (e) {
      setItemError(errorMessage(e));
    } finally {
      setItemBusy(false);
    }
  };

  const pickRejectCode = (code: RemovalReason) => {
    setRejectCode(code);
    const label = REMOVAL_REASONS.find((r) => r.value === code)?.label ?? "";
    // Sirf tab badlo jab seller ne apna likha hua na ho
    if (REMOVAL_REASONS.some((r) => r.label === rejectText) || rejectText === "Saman abhi dukaan me nahi hai") {
      setRejectText(code === "OUT_OF_STOCK" ? "Saman abhi dukaan me nahi hai" : code === "OTHER" ? "" : label);
    }
  };

  const submitReject = async () => {
    if (!order) return;
    setRejectBusy(true);
    setRejectError("");
    try {
      setOrder(await rejectOrder(order.id, rejectText.trim(), rejectCode));
      setRejectOpen(false);
    } catch (e) {
      setRejectError(errorMessage(e));
    } finally {
      setRejectBusy(false);
    }
  };

  if (loading) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.canvas }}>
        <SellerHeader title="Order" onBack={() => (router.canGoBack() ? router.back() : router.replace("/seller"))} />
        <Spinner />
      </View>
    );
  }
  if (!order) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.canvas }}>
        <SellerHeader title="Order" onBack={() => (router.canGoBack() ? router.back() : router.replace("/seller"))} />
        <EmptyState title={loadError || "Order nahi mila"} action={<Button label="Dobara try karein" onPress={load} variant="ghost" />} />
      </View>
    );
  }

  const st = STORE_ORDER_STATUS[order.status];
  const canRemoveItems = order.status === "PLACED";

  return (
    <View style={{ flex: 1, backgroundColor: colors.canvas }}>
      <SellerHeader title={`Order #${order.order_number}`} subtitle={formatDateTime(order.created_at)} onBack={() => (router.canGoBack() ? router.back() : router.replace("/seller"))} />
      <ScrollView contentContainerStyle={{ padding: space.lg, paddingBottom: insets.bottom + space.xxl }}>
        <View style={{ flexDirection: "row", alignItems: "center" }}>
          <Badge label={st.label} tone={st.tone} />
          <View style={{ width: space.sm }} />
          <Badge label={paymentLabel(order.payment_method)} />
        </View>

        <Text style={{ ...type.heading, color: colors.text, marginTop: space.lg, marginBottom: space.sm }}>Saman</Text>
        <Card style={{ padding: 0 }}>
          {order.items.map((it, i) => (
            <View
              key={it.id}
              style={{
                padding: space.lg,
                borderTopWidth: i === 0 ? 0 : 1,
                borderTopColor: colors.line,
                opacity: it.removed && it.removed_kept_quantity == null ? 0.6 : 1,
              }}
            >
              <View style={{ flexDirection: "row" }}>
                <View style={{ flex: 1 }}>
                  <Text
                    style={{
                      ...type.heading,
                      color: colors.text,
                      textDecorationLine: it.removed && !it.removed_kept_quantity ? "line-through" : "none",
                    }}
                  >
                    {it.name}
                  </Text>
                  <Text style={{ ...type.caption, color: colors.textMuted }}>
                    {it.selling_unit} · {formatPrice(it.unit_price)} × {it.quantity}
                  </Text>
                </View>
                <Text style={{ ...type.heading, color: colors.text }}>{formatPrice(it.line_total)}</Text>
              </View>
              {it.removed && (
                <Text style={{ ...type.caption, color: colors.danger, marginTop: 2 }}>
                  {it.removed_kept_quantity
                    ? `Sirf ${it.removed_kept_quantity} diye`
                    : "Hata diya"}
                  {it.removed_reason ? ` · ${it.removed_reason}` : ""}
                </Text>
              )}
              {canRemoveItems && !it.removed && (
                <Pressable onPress={() => openItem(it)} hitSlop={8} style={{ alignSelf: "flex-start", marginTop: space.sm }}>
                  <Text style={{ ...type.body, color: colors.danger }}>Ye saman nahi hai</Text>
                </Pressable>
              )}
            </View>
          ))}
        </Card>

        <Card style={{ marginTop: space.lg }}>
          <KV k="Saman ka total" v={formatPrice(order.items_subtotal)} bold />
          {order.seller_discount > 0 && (
            <KV k="Aapka coupon discount (payout se katega)" v={`− ${formatPrice(order.seller_discount)}`} color={colors.danger} />
          )}
          <Text style={{ ...type.caption, color: colors.textMuted, marginTop: space.xs }}>
            Customer ka number aur pata seller ko nahi dikhta. Delivery partner use sambhalta hai.
          </Text>
        </Card>

        <ErrorText>{error}</ErrorText>

        <View style={{ marginTop: space.xl }}>
          {order.status === "PLACED" && (
            <>
              <Button label="Order le lein" onPress={() => step("accept")} loading={busy === "accept"} />
              <View style={{ height: space.sm }} />
              <Button
                label="Poora order mana karein"
                onPress={() => {
                  setRejectError("");
                  setRejectOpen(true);
                }}
                variant="ghost"
              />
              <Text style={{ ...type.caption, color: colors.textMuted, textAlign: "center", marginTop: space.sm }}>
                Koi saman na ho to pehle “Ye saman nahi hai” dabayein. Saman hatane ke baad customer ko cancel ka mauka dene ke liye order lene se pehle 2 minute rukna padta hai.
              </Text>
            </>
          )}
          {order.status === "SELLER_ACCEPTED" && (
            <>
              <Button label="Saman ready hai" onPress={() => step("ready")} loading={busy === "ready"} />
              <View style={{ height: space.sm }} />
              <Button label="Taiyaar ho raha hai" onPress={() => step("preparing")} loading={busy === "preparing"} variant="ghost" />
            </>
          )}
          {order.status === "PREPARING" && (
            <Button label="Saman ready hai" onPress={() => step("ready")} loading={busy === "ready"} />
          )}
          {order.status === "READY_FOR_PICKUP" && (
            <Card style={{ backgroundColor: "#DDF1E4" }}>
              <Text style={{ ...type.body, color: colors.success }}>
                Saman ready hai. Delivery partner aakar le jayega.
              </Text>
            </Card>
          )}
        </View>
      </ScrollView>

      {/* Ek saman nahi hai */}
      <Sheet visible={!!item} onClose={() => setItem(null)} title="Ye saman nahi hai">
        {item && (
          <>
            <Text style={{ ...type.heading, color: colors.text }}>{item.name}</Text>
            <Text style={{ ...type.caption, color: colors.textMuted }}>Customer ne {item.quantity} maange hain</Text>

            <Text style={{ ...type.caption, color: colors.textMuted, marginTop: space.lg, marginBottom: space.sm }}>Wajah</Text>
            <Chips wrap value={itemReason} onChange={setItemReason} options={REMOVAL_REASONS} />

            {item.quantity > 1 && (
              <>
                <Text style={{ ...type.caption, color: colors.textMuted, marginTop: space.md }}>
                  Kitne de sakte hain? (0 = ek bhi nahi)
                </Text>
                <View style={{ flexDirection: "row", alignItems: "center", marginTop: space.sm }}>
                  <Pressable
                    onPress={() => setKeepQty((q) => Math.max(0, q - 1))}
                    style={{ width: 40, height: 40, borderRadius: 20, borderWidth: 1.5, borderColor: colors.ink, alignItems: "center", justifyContent: "center" }}
                  >
                    <Text style={{ ...type.title, color: colors.ink }}>−</Text>
                  </Pressable>
                  <Text style={{ ...type.title, color: colors.text, width: 60, textAlign: "center" }}>{keepQty}</Text>
                  <Pressable
                    onPress={() => setKeepQty((q) => Math.min(item.quantity - 1, q + 1))}
                    style={{ width: 40, height: 40, borderRadius: 20, borderWidth: 1.5, borderColor: colors.ink, alignItems: "center", justifyContent: "center" }}
                  >
                    <Text style={{ ...type.title, color: colors.ink }}>+</Text>
                  </Pressable>
                </View>
              </>
            )}

            <Field label="Customer ke liye note (zaroori nahi)" value={itemNote} onChangeText={setItemNote} maxLength={200} />
            <ErrorText>{itemError}</ErrorText>
            <View style={{ marginTop: space.xl }}>
              <Button label={keepQty > 0 ? `Sirf ${keepQty} denge` : "Is saman ko hatayein"} onPress={submitItem} loading={itemBusy} />
            </View>
          </>
        )}
      </Sheet>

      {/* Poora order mana */}
      <Sheet visible={rejectOpen} onClose={() => setRejectOpen(false)} title="Order mana karein">
        <Text style={{ ...type.body, color: colors.textMuted }}>
          Customer ko ye wajah dikhegi. Saman ka stock wapas jud jayega.
        </Text>
        <Text style={{ ...type.caption, color: colors.textMuted, marginTop: space.lg, marginBottom: space.sm }}>Wajah</Text>
        <Chips wrap value={rejectCode} onChange={pickRejectCode} options={REMOVAL_REASONS} />
        <Field
          label="Customer ko kya dikhana hai"
          value={rejectText}
          onChangeText={setRejectText}
          maxLength={200}
          placeholder="Wajah likhein"
        />
        <ErrorText>{rejectError}</ErrorText>
        <View style={{ marginTop: space.xl }}>
          <Button label="Order mana karein" onPress={submitReject} loading={rejectBusy} disabled={rejectText.trim().length < 3} />
        </View>
      </Sheet>
    </View>
  );
}
