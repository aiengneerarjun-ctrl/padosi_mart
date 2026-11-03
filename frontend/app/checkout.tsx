import { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, Alert, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { useFocusEffect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { ApiError, errorMessage } from "../src/api/client";
import { CheckoutPreview, CouponOut, listCoupons, previewCheckout } from "../src/api/checkout";
import { placeOrder as placeOrderApi } from "../src/api/orders";
import { useCart } from "../src/cart/CartContext";
import { Button } from "../src/components/Button";
import { IconButton } from "../src/components/IconButton";
import { formatPrice } from "../src/lib/media";
import { newUuid } from "../src/lib/uuid";
import { colors, radius, space, type } from "../src/theme";

const LABEL_TEXT: Record<string, string> = { HOME: "Ghar", WORK: "Office", OTHER: "Doosra" };

function BillRow({ label, value, color, bold }: { label: string; value: string; color?: string; bold?: boolean }) {
  return (
    <View style={{ flexDirection: "row", justifyContent: "space-between", paddingVertical: 4 }}>
      <Text style={{ ...(bold ? type.heading : type.body), color: bold ? colors.text : colors.textMuted }}>{label}</Text>
      <Text style={{ ...(bold ? type.heading : type.body), color: color ?? colors.text }}>{value}</Text>
    </View>
  );
}

function couponLine(c: CouponOut): string {
  if (c.discount_type === "FREE_DELIVERY") return "Free delivery";
  if (c.discount_type === "PERCENT") {
    return `${c.value}% off${c.max_discount ? ` (zyada se zyada ${formatPrice(c.max_discount)})` : ""}`;
  }
  return `${formatPrice(c.value)} off`;
}

export default function CheckoutScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { refresh: refreshCart } = useCart();

  const [preview, setPreview] = useState<CheckoutPreview | null>(null);
  const [error, setError] = useState<{ code?: string; message: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const [coupons, setCoupons] = useState<CouponOut[]>([]);
  const [codeInput, setCodeInput] = useState("");
  const [applied, setApplied] = useState<string | null>(null);

  const idemKey = useRef(newUuid()); // is checkout ki key: retry me wahi, duplicate order nahi banega
  const [note, setNote] = useState("");
  const [method, setMethod] = useState<"COD" | "ONLINE">("COD");
  const [placing, setPlacing] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      setPreview(await previewCheckout(applied));
      setError(null);
    } catch (e) {
      setPreview(null);
      setError({ code: e instanceof ApiError ? e.code : undefined, message: errorMessage(e) });
    } finally {
      setBusy(false);
    }
  }, [applied]);

  // Screen par aate hi (aur address se wapas aane par) hisaab taza karo
  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  useEffect(() => {
    listCoupons()
      .then(setCoupons)
      .catch(() => {});
  }, []);

  const applyCode = (code: string) => {
    const c = code.trim().toUpperCase();
    if (!c) return;
    setCodeInput(c);
    setApplied(c);
  };
  const removeCode = () => {
    setApplied(null);
    setCodeInput("");
  };

  const placeOrder = async () => {
    if (!preview || placing) return;
    setPlacing(true);
    try {
      const order = await placeOrderApi(
        {
          address_id: preview.address.id,
          payment_method: method,
          expected_total: Number(preview.total.toFixed(2)),
          coupon_code: preview.coupon && !preview.coupon_error ? preview.coupon.code : undefined,
          note: note.trim() || undefined,
        },
        idemKey.current,
      );
      await refreshCart();
      router.dismissAll(); // checkout aur cart band, wapas Home
      router.push({ pathname: "/order/[id]", params: { id: order.id } });
      if (method === "ONLINE") router.push({ pathname: "/pay/[id]", params: { id: order.id } });
    } catch (e) {
      const code = e instanceof ApiError ? e.code : "";
      Alert.alert("Order", errorMessage(e));
      if (code === "PAYMENT_METHOD_NOT_AVAILABLE") {
        setMethod("COD"); // online abhi chalu nahi: COD par wapas
        return;
      }
      if (code === "CART_HAS_UNAVAILABLE_ITEMS" || code === "ORDER_ITEMS_CHANGED" || code === "CART_EMPTY") {
        refreshCart();
        router.push("/cart");
      } else {
        load(); // PRICE_CHANGED ya coupon ki dikkat: hisaab dobara lao
      }
    } finally {
      setPlacing(false);
    }
  };

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
      <Text style={{ ...type.title, color: colors.onInk, marginLeft: space.md }}>Checkout</Text>
    </View>
  );

  if (!preview && !error) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.canvas }}>
        {topBar}
        <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
          <ActivityIndicator color={colors.ink} />
        </View>
      </View>
    );
  }

  if (error?.code === "ADDRESS_REQUIRED") {
    return (
      <View style={{ flex: 1, backgroundColor: colors.canvas }}>
        {topBar}
        <View style={{ flex: 1, alignItems: "center", justifyContent: "center", padding: space.xl }}>
          <Text style={{ ...type.title, color: colors.text }}>Delivery address chahiye</Text>
          <Text style={{ ...type.body, color: colors.textMuted, textAlign: "center", marginTop: space.xs }}>
            Saman kahan pahunchana hai, ye pehle batayein.
          </Text>
          <View style={{ marginTop: space.xl, width: "100%" }}>
            <Button label="Address jodein" onPress={() => router.push("/address-new")} />
          </View>
        </View>
      </View>
    );
  }

  if (error || !preview) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.canvas }}>
        {topBar}
        <View style={{ flex: 1, alignItems: "center", justifyContent: "center", padding: space.xl }}>
          <Text style={{ ...type.body, color: colors.danger, textAlign: "center" }}>{error?.message}</Text>
          <Pressable onPress={load} style={{ marginTop: space.lg }}>
            <Text style={{ ...type.heading, color: colors.ink }}>Dobara try karein</Text>
          </Pressable>
        </View>
      </View>
    );
  }

  const a = preview.address;
  const couponOk = !!preview.coupon && !preview.coupon_error;
  const empty = preview.blockers.includes("CART_EMPTY");
  const unavailable = preview.blockers.includes("ITEM_UNAVAILABLE");

  return (
    <View style={{ flex: 1, backgroundColor: colors.canvas }}>
      {topBar}
      <ScrollView
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={{ padding: space.lg, paddingBottom: insets.bottom + 140 }}
        showsVerticalScrollIndicator={false}
      >
        {/* Address */}
        <View
          style={{
            backgroundColor: colors.surface,
            borderWidth: 1,
            borderColor: colors.line,
            borderRadius: radius.md,
            padding: space.lg,
            marginBottom: space.lg,
          }}
        >
          <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
            <Text style={{ ...type.caption, color: colors.textMuted }}>Delivery address · {LABEL_TEXT[a.label] ?? a.label}</Text>
            <Pressable onPress={() => router.push("/addresses")} hitSlop={10}>
              <Text style={{ ...type.body, color: colors.ink }}>Badlein</Text>
            </Pressable>
          </View>
          <Text style={{ ...type.heading, color: colors.text, marginTop: 2 }}>
            {a.receiver_name} · {a.receiver_phone}
          </Text>
          <Text style={{ ...type.body, color: colors.textMuted }}>{a.address_line}</Text>
          {!!a.landmark && <Text style={{ ...type.caption, color: colors.textMuted }}>Landmark: {a.landmark}</Text>}
        </View>

        {/* Problem ho to */}
        {(empty || unavailable) && (
          <View style={{ backgroundColor: "#F7DAD7", borderRadius: radius.md, padding: space.lg, marginBottom: space.lg }}>
            <Text style={{ ...type.body, color: colors.danger }}>
              {empty
                ? "Cart khali hai."
                : "Is address par kuch items available nahi hain. Cart me jaakar unhe hatayein."}
            </Text>
            <Pressable onPress={() => router.push("/cart")} style={{ marginTop: space.sm }}>
              <Text style={{ ...type.heading, color: colors.ink }}>Cart par jaayein</Text>
            </Pressable>
          </View>
        )}

        {/* Items */}
        {preview.stores.map((g) => (
          <View
            key={g.store_id}
            style={{
              backgroundColor: colors.surface,
              borderWidth: 1,
              borderColor: colors.line,
              borderRadius: radius.md,
              padding: space.lg,
              marginBottom: space.md,
            }}
          >
            <Text style={{ ...type.heading, color: colors.text }}>{g.store_name}</Text>
            {g.items.map((it) => (
              <View key={it.product_id} style={{ flexDirection: "row", justifyContent: "space-between", marginTop: space.sm }}>
                <View style={{ flex: 1, paddingRight: space.md }}>
                  <Text numberOfLines={2} style={{ ...type.body, color: it.available ? colors.text : colors.textMuted }}>
                    {it.name} × {it.quantity}
                  </Text>
                  {!it.available && <Text style={{ ...type.caption, color: colors.danger }}>Available nahi</Text>}
                </View>
                <Text style={{ ...type.body, color: it.available ? colors.text : colors.textMuted }}>
                  {formatPrice(it.line_total)}
                </Text>
              </View>
            ))}
          </View>
        ))}

        {/* Coupon */}
        <Text style={{ ...type.heading, color: colors.text, marginTop: space.lg, marginBottom: space.sm }}>Coupon</Text>
        {couponOk ? (
          <View
            style={{
              flexDirection: "row",
              alignItems: "center",
              justifyContent: "space-between",
              backgroundColor: "#DDF1E4",
              borderRadius: radius.md,
              padding: space.lg,
            }}
          >
            <View style={{ flex: 1 }}>
              <Text style={{ ...type.heading, color: colors.success }}>{preview.coupon!.code} laga diya</Text>
              <Text style={{ ...type.caption, color: colors.success }}>{preview.coupon!.title}</Text>
            </View>
            <Pressable onPress={removeCode} hitSlop={10}>
              <Text style={{ ...type.body, color: colors.danger }}>Hatayein</Text>
            </Pressable>
          </View>
        ) : (
          <>
            <View style={{ flexDirection: "row", alignItems: "center" }}>
              <TextInput
                value={codeInput}
                onChangeText={(v) => setCodeInput(v.toUpperCase())}
                autoCapitalize="characters"
                maxLength={20}
                placeholder="Coupon code"
                placeholderTextColor={colors.textMuted}
                style={{
                  ...type.body,
                  flex: 1,
                  color: colors.text,
                  backgroundColor: colors.surface,
                  borderWidth: 1.5,
                  borderColor: applied && preview.coupon_error ? colors.danger : colors.line,
                  borderRadius: radius.md,
                  paddingHorizontal: space.lg,
                  paddingVertical: 12,
                }}
              />
              <Pressable
                onPress={() => applyCode(codeInput)}
                disabled={!codeInput.trim()}
                style={{
                  marginLeft: space.sm,
                  backgroundColor: colors.ink,
                  borderRadius: radius.md,
                  paddingHorizontal: space.lg,
                  paddingVertical: 14,
                  opacity: codeInput.trim() ? 1 : 0.45,
                }}
              >
                <Text style={{ ...type.heading, color: colors.onInk }}>Lagayein</Text>
              </Pressable>
            </View>
            {!!applied && !!preview.coupon_error && (
              <Text style={{ ...type.caption, color: colors.danger, marginTop: space.xs }}>
                {preview.coupon_message ?? "Ye coupon abhi nahi chal sakta."}
              </Text>
            )}
          </>
        )}

        {coupons.length > 0 && !couponOk && (
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            style={{ marginTop: space.md, marginHorizontal: -space.lg }}
            contentContainerStyle={{ paddingHorizontal: space.lg }}
          >
            {coupons.map((c) => (
              <Pressable
                key={c.id}
                onPress={() => c.usable && applyCode(c.code)}
                style={{
                  width: 210,
                  marginRight: space.md,
                  backgroundColor: colors.surface,
                  borderWidth: 1,
                  borderColor: colors.line,
                  borderRadius: radius.md,
                  padding: space.md,
                  opacity: c.usable ? 1 : 0.55,
                }}
              >
                <Text style={{ ...type.heading, color: colors.marigoldDeep }}>{c.code}</Text>
                <Text numberOfLines={1} style={{ ...type.body, color: colors.text }}>
                  {c.title}
                </Text>
                <Text style={{ ...type.caption, color: colors.textMuted }}>{couponLine(c)}</Text>
                {c.min_order_amount > 0 && (
                  <Text style={{ ...type.caption, color: colors.textMuted }}>
                    Kam se kam {formatPrice(c.min_order_amount)} ka saman
                  </Text>
                )}
                {!c.usable && !!c.unusable_message && (
                  <Text style={{ ...type.caption, color: colors.danger, marginTop: 2 }}>{c.unusable_message}</Text>
                )}
              </Pressable>
            ))}
          </ScrollView>
        )}

        {/* Payment aur note */}
        <Text style={{ ...type.heading, color: colors.text, marginTop: space.xl, marginBottom: space.sm }}>Payment</Text>
        {(
          [
            { v: "COD", title: "Delivery par cash (COD)", sub: "Saman milne par paisa dein." },
            { v: "ONLINE", title: "Online payment", sub: "UPI, card ya net banking se abhi dein." },
          ] as const
        ).map((o) => {
          const on = method === o.v;
          return (
            <Pressable
              key={o.v}
              onPress={() => setMethod(o.v)}
              style={{
                flexDirection: "row",
                alignItems: "center",
                backgroundColor: colors.surface,
                borderWidth: on ? 2 : 1,
                borderColor: on ? colors.ink : colors.line,
                borderRadius: radius.md,
                padding: space.lg,
                marginBottom: space.sm,
              }}
            >
              <View
                style={{
                  width: 22,
                  height: 22,
                  borderRadius: 11,
                  borderWidth: 2,
                  borderColor: on ? colors.ink : colors.line,
                  alignItems: "center",
                  justifyContent: "center",
                  marginRight: space.md,
                }}
              >
                {on && <View style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: colors.ink }} />}
              </View>
              <View style={{ flex: 1 }}>
                <Text style={{ ...type.heading, color: colors.text }}>{o.title}</Text>
                <Text style={{ ...type.caption, color: colors.textMuted }}>{o.sub}</Text>
              </View>
            </Pressable>
          );
        })}

        <TextInput
          value={note}
          onChangeText={setNote}
          maxLength={300}
          placeholder="Delivery ke liye koi note (zaroori nahi)"
          placeholderTextColor={colors.textMuted}
          style={{
            ...type.body,
            color: colors.text,
            backgroundColor: colors.surface,
            borderWidth: 1.5,
            borderColor: colors.line,
            borderRadius: radius.md,
            paddingHorizontal: space.lg,
            paddingVertical: 12,
            marginTop: space.sm,
          }}
        />

        {/* Hisaab */}
        <Text style={{ ...type.heading, color: colors.text, marginTop: space.xl, marginBottom: space.sm }}>Bill</Text>
        <View
          style={{
            backgroundColor: colors.surface,
            borderWidth: 1,
            borderColor: colors.line,
            borderRadius: radius.md,
            padding: space.lg,
          }}
        >
          <BillRow label={`Saman ka total (${preview.item_count} item)`} value={formatPrice(preview.items_subtotal)} />
          <BillRow
            label="Delivery charge"
            value={preview.delivery_fee > 0 ? formatPrice(preview.delivery_fee) : "Free"}
            color={preview.delivery_fee > 0 ? undefined : colors.success}
          />
          {preview.discount_amount > 0 && (
            <BillRow label="Coupon discount" value={`- ${formatPrice(preview.discount_amount)}`} color={colors.success} />
          )}
          <View style={{ height: 1, backgroundColor: colors.line, marginVertical: space.sm }} />
          <BillRow label="Kul total" value={formatPrice(preview.total)} bold />
        </View>

        {preview.free_delivery_remaining > 0 && (
          <Text style={{ ...type.caption, color: colors.marigoldDeep, marginTop: space.sm }}>
            {formatPrice(preview.free_delivery_remaining)} ka saman aur jodein, {formatPrice(preview.free_delivery_from)} se
            upar delivery free hai.
          </Text>
        )}
      </ScrollView>

      {/* Neeche ka bar */}
      <View
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: colors.surface,
          borderTopWidth: 1,
          borderTopColor: colors.line,
          padding: space.lg,
          paddingBottom: insets.bottom + space.md,
          flexDirection: "row",
          alignItems: "center",
        }}
      >
        <View style={{ flex: 1 }}>
          <Text style={{ ...type.caption, color: colors.textMuted }}>Kul total</Text>
          <Text style={{ ...type.title, color: colors.text }}>{formatPrice(preview.total)}</Text>
        </View>
        <View style={{ flex: 1.2 }}>
          <Button
            label={method === "ONLINE" ? "Payment karein" : "Order karein"}
            onPress={placeOrder}
            loading={busy || placing}
            disabled={!preview.can_checkout}
          />
        </View>
      </View>
    </View>
  );
}