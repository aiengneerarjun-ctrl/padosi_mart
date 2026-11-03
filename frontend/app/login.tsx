import { useState } from "react";
import { KeyboardAvoidingView, Platform, Pressable, SafeAreaView, Text, TextInput, View } from "react-native";
import { useRouter } from "expo-router";
import { requestOtp } from "../src/api/auth";
import { errorMessage } from "../src/api/client";
import { Button } from "../src/components/Button";
import { LanguageSelector } from "../src/components/LanguageSelector";
import { colors, radius, space, type } from "../src/theme";

type Role = "customer" | "seller" | "delivery";

const ROLES: { value: Role; title: string; sub: string }[] = [
  { value: "customer", title: "Main customer hoon", sub: "Saman mangwana hai" },
  { value: "seller", title: "Main seller hoon", sub: "Apni dukaan chalani hai" },
  { value: "delivery", title: "Main delivery partner hoon", sub: "Orders deliver karne hain" },
];

export default function Login() {
  const router = useRouter();
  const [role, setRole] = useState<Role>("customer");
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const valid = /^[6-9]\d{9}$/.test(phone);

  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      await requestOtp(phone);
      router.push({ pathname: "/otp", params: { phone, role } });
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.ink }}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <View style={{ flex: 1, padding: space.xl, justifyContent: "flex-end" }}>
          <Text style={{ ...type.display, color: colors.onInk, fontSize: 44, lineHeight: 50 }}>Padosi</Text>
          <Text style={{ ...type.body, color: "#B9D3CF", marginTop: space.sm }}>
            Aapke mohalle ki dukaanein, ghar tak.
          </Text>
        </View>

        <View
          style={{
            backgroundColor: colors.surface,
            borderTopLeftRadius: radius.lg,
            borderTopRightRadius: radius.lg,
            padding: space.xl,
            paddingBottom: space.xxl,
          }}
        >
          <LanguageSelector />

          {/* Customer ya seller */}
          <View style={{ flexDirection: "row", marginBottom: space.lg }}>
            {ROLES.map((r, i) => {
              const on = role === r.value;
              return (
                <Pressable
                  key={r.value}
                  onPress={() => setRole(r.value)}
                  style={{
                    flex: 1,
                    marginLeft: i === 0 ? 0 : space.sm,
                    backgroundColor: on ? colors.ink : colors.surface,
                    borderWidth: 1.5,
                    borderColor: on ? colors.ink : colors.line,
                    borderRadius: radius.md,
                    padding: space.md,
                  }}
                >
                  <Text style={{ ...type.heading, color: on ? colors.onInk : colors.text }}>{r.title}</Text>
                  <Text style={{ ...type.caption, color: on ? "#B9D3CF" : colors.textMuted }}>{r.sub}</Text>
                </Pressable>
              );
            })}
          </View>

          <Text style={{ ...type.title, color: colors.text }}>Mobile number daalein</Text>
          <Text style={{ ...type.body, color: colors.textMuted, marginTop: space.xs }}>
            Hum ek OTP bhejenge. Alag se password nahi chahiye.
          </Text>

          <View
            style={{
              flexDirection: "row",
              alignItems: "center",
              marginTop: space.lg,
              borderWidth: 1.5,
              borderColor: error ? colors.danger : colors.line,
              borderRadius: radius.md,
              paddingHorizontal: space.lg,
            }}
          >
            <Text style={{ ...type.heading, color: colors.textMuted }}>+91</Text>
            <TextInput
              value={phone}
              onChangeText={(v) => {
                setPhone(v.replace(/\D/g, "").slice(0, 10));
                setError("");
              }}
              keyboardType="number-pad"
              placeholder="10 digit number"
              placeholderTextColor={colors.textMuted}
              maxLength={10}
              style={{ ...type.heading, flex: 1, marginLeft: space.md, paddingVertical: 14, color: colors.text }}
            />
          </View>

          {!!error && <Text style={{ ...type.caption, color: colors.danger, marginTop: space.sm }}>{error}</Text>}

          <View style={{ marginTop: space.lg }}>
            <Button label="OTP bhejein" onPress={submit} loading={busy} disabled={!valid} />
          </View>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
