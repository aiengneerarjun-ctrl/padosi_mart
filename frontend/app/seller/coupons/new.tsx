import { useState } from "react";
import { KeyboardAvoidingView, Platform, ScrollView, Switch, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { errorMessage } from "../../../src/api/client";
import { createCoupon } from "../../../src/api/sellerMoney";
import { Button } from "../../../src/components/Button";
import { Chips, ErrorText, Field, SellerHeader, toNumber } from "../../../src/components/seller/ui";
import { colors, space, type } from "../../../src/theme";

const CODE_RE = /^[A-Z0-9_-]{3,20}$/;
const DAY_MS = 24 * 60 * 60 * 1000;

// "0" bhi chalega (min order ke liye), paise tak
function moneyOrZero(s: string): string | null {
  const t = s.replace(/,/g, ".").trim();
  return /^\d+(\.\d{1,2})?$/.test(t) ? t : null;
}

export default function NewCoupon() {
  const router = useRouter();
  const insets = useSafeAreaInsets();

  const [code, setCode] = useState("");
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState<"FLAT" | "PERCENT">("FLAT");
  const [value, setValue] = useState("");
  const [maxDiscount, setMaxDiscount] = useState("");
  const [minOrder, setMinOrder] = useState("0");
  const [days, setDays] = useState(30);
  const [perUser, setPerUser] = useState(1);
  const [totalLimit, setTotalLimit] = useState("");
  const [firstOnly, setFirstOnly] = useState(false);
  const [isPublic, setIsPublic] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const valueN = toNumber(value);
  const valueOk = Number.isFinite(valueN) && valueN > 0 && (kind === "FLAT" || valueN <= 100) && !!moneyOrZero(value);
  const maxOk = kind !== "PERCENT" || maxDiscount.trim() === "" || (!!moneyOrZero(maxDiscount) && toNumber(maxDiscount) > 0);
  const minOk = !!moneyOrZero(minOrder);
  const limitN = totalLimit.trim() === "" ? null : toNumber(totalLimit);
  const limitOk = limitN === null || (Number.isInteger(limitN) && limitN >= 1);
  const valid = CODE_RE.test(code) && title.trim().length >= 3 && valueOk && maxOk && minOk && limitOk;

  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      await createCoupon({
        code,
        title: title.trim(),
        discount_type: kind,
        value: moneyOrZero(value) ?? "0",
        max_discount: kind === "PERCENT" && maxDiscount.trim() ? moneyOrZero(maxDiscount) : null,
        min_order_amount: moneyOrZero(minOrder) ?? "0",
        first_order_only: firstOnly,
        is_public: isPublic,
        per_user_limit: perUser,
        total_limit: limitN,
        expires_at: new Date(Date.now() + days * DAY_MS).toISOString(),
      });
      (router.canGoBack() ? router.back() : router.replace("/seller"));
    } catch (e) {
      setError(errorMessage(e));
      setBusy(false);
    }
  };

  const toggleRow = (label: string, sub: string, v: boolean, on: (b: boolean) => void) => (
    <View style={{ flexDirection: "row", alignItems: "center", marginTop: space.lg }}>
      <View style={{ flex: 1, marginRight: space.md }}>
        <Text style={{ ...type.heading, color: colors.text }}>{label}</Text>
        <Text style={{ ...type.caption, color: colors.textMuted }}>{sub}</Text>
      </View>
      <Switch value={v} onValueChange={on} trackColor={{ false: colors.line, true: colors.success }} />
    </View>
  );

  return (
    <View style={{ flex: 1, backgroundColor: colors.canvas }}>
      <SellerHeader title="Naya coupon" subtitle="Banne ke baad discount ka niyam badalta nahi" onBack={() => (router.canGoBack() ? router.back() : router.replace("/seller"))} />
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <ScrollView
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={{ padding: space.lg, paddingBottom: insets.bottom + space.xxl }}
        >
          <Field
            label="Coupon code"
            value={code}
            onChangeText={(v) => setCode(v.toUpperCase().replace(/[^A-Z0-9_-]/g, "").slice(0, 20))}
            autoCapitalize="characters"
            autoCorrect={false}
            placeholder="DIWALI50"
            hint="3 se 20 akshar: A-Z, 0-9, - ya _"
          />
          <Field
            label="Customer ko kya dikhega"
            value={title}
            onChangeText={setTitle}
            maxLength={120}
            placeholder="Jaise Diwali par ₹50 ki chhoot"
          />

          <Text style={{ ...type.caption, color: colors.textMuted, marginTop: space.lg, marginBottom: space.sm }}>Chhoot ka tarika</Text>
          <Chips
            wrap
            value={kind}
            onChange={setKind}
            options={[
              { value: "FLAT" as const, label: "Seedhe ₹ kam" },
              { value: "PERCENT" as const, label: "Percent kam" },
            ]}
          />
          <Field
            label={kind === "FLAT" ? "Kitne rupaye kam" : "Kitne percent kam"}
            value={value}
            onChangeText={setValue}
            keyboardType="decimal-pad"
            prefix={kind === "FLAT" ? "₹" : "%"}
            error={value && !valueOk ? (kind === "PERCENT" ? "1 se 100 ke beech" : "0 se zyada likhein") : undefined}
          />
          {kind === "PERCENT" && (
            <Field
              label="Zyada se zyada kitni chhoot (zaroori nahi)"
              value={maxDiscount}
              onChangeText={setMaxDiscount}
              keyboardType="decimal-pad"
              prefix="₹"
              hint="Jaise 20% par maximum ₹100"
              error={maxDiscount && !maxOk ? "Sahi rakam likhein" : undefined}
            />
          )}
          <Field
            label="Kam se kam order"
            value={minOrder}
            onChangeText={setMinOrder}
            keyboardType="decimal-pad"
            prefix="₹"
            hint="0 rakhein to har order par chalega"
          />

          <Text style={{ ...type.caption, color: colors.textMuted, marginTop: space.lg, marginBottom: space.sm }}>Kitne din chalega</Text>
          <Chips
            wrap
            value={days}
            onChange={setDays}
            options={[7, 15, 30, 60, 90].map((d) => ({ value: d, label: `${d} din` }))}
          />

          <Text style={{ ...type.caption, color: colors.textMuted, marginTop: space.lg, marginBottom: space.sm }}>
            Ek customer kitni baar laga sakta hai
          </Text>
          <Chips wrap value={perUser} onChange={setPerUser} options={[1, 2, 3, 5].map((n) => ({ value: n, label: `${n} baar` }))} />

          <Field
            label="Kul kitni baar chalega (zaroori nahi)"
            value={totalLimit}
            onChangeText={(v) => setTotalLimit(v.replace(/\D/g, ""))}
            keyboardType="number-pad"
            hint="Khali chhodein to koi had nahi"
          />

          {toggleRow("Sirf pehle order par", "Naye customer ko lubhane ke liye", firstOnly, setFirstOnly)}
          {toggleRow("Sab ko dikhe", "Band karne par sirf code jaanne wale laga payenge", isPublic, setIsPublic)}

          <Text style={{ ...type.caption, color: colors.textMuted, marginTop: space.xl }}>
            Ye chhoot aapke payout se kategi aur sirf aapke saman par lagegi. Free delivery seller nahi de sakta.
          </Text>

          <ErrorText>{error}</ErrorText>
          <View style={{ marginTop: space.lg }}>
            <Button label="Coupon banayein" onPress={submit} loading={busy} disabled={!valid} />
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </View>
  );
}
