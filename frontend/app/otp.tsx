import { useEffect, useState } from "react";
import { KeyboardAvoidingView, Platform, SafeAreaView, Text, TextInput, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { requestOtp, verifyOtp } from "../src/api/auth";
import { errorMessage } from "../src/api/client";
import { useAuth } from "../src/auth/AuthContext";
import { Button } from "../src/components/Button";
import { colors, radius, space, type } from "../src/theme";

const RESEND_SECONDS = 30;

export default function Otp() {
  const router = useRouter();
  const { signIn, setMode } = useAuth();
  const { phone, role } = useLocalSearchParams<{ phone: string; role?: string }>();

  const [otp, setOtp] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [wait, setWait] = useState(RESEND_SECONDS);

  useEffect(() => {
    if (wait <= 0) return;
    const id = setTimeout(() => setWait((w) => w - 1), 1000);
    return () => clearTimeout(id);
  }, [wait]);

  const submit = async (code: string) => {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const tokens = await verifyOtp(phone, code);
      const mode = role === "seller" || role === "delivery" ? role : "customer";
      await setMode(mode); // login ke saath hi chuna hua dashboard khulega
      await signIn(tokens);
      // Auth gate protected routes kholta hai; replace OTP ko back stack se bhi hata deta hai.
      router.replace(mode === "seller" ? "/seller" : mode === "delivery" ? "/delivery" : "/");
    } catch (e) {
      setError(errorMessage(e));
      setOtp("");
      setBusy(false);
    }
  };

  const resend = async () => {
    setError("");
    try {
      await requestOtp(phone);
      setWait(RESEND_SECONDS);
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.ink }}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <View style={{ flex: 1, padding: space.xl, justifyContent: "flex-end" }}>
          <Text style={{ ...type.display, color: colors.onInk }}>OTP daalein</Text>
          <Text style={{ ...type.body, color: "#B9D3CF", marginTop: space.sm }}>+91 {phone} par 6 digit ka code gaya hai.</Text>
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
          <TextInput
            value={otp}
            onChangeText={(v) => {
              const d = v.replace(/\D/g, "").slice(0, 6);
              setOtp(d);
              setError("");
              if (d.length === 6) submit(d);
            }}
            keyboardType="number-pad"
            maxLength={6}
            autoFocus
            editable={!busy}
            placeholder="------"
            placeholderTextColor={colors.line}
            style={{
              fontFamily: type.title.fontFamily,
              fontSize: 32,
              letterSpacing: 14,
              textAlign: "center",
              color: colors.text,
              borderWidth: 1.5,
              borderColor: error ? colors.danger : colors.line,
              borderRadius: radius.md,
              paddingVertical: 14,
            }}
          />

          {!!error && (
            <Text style={{ ...type.caption, color: colors.danger, marginTop: space.sm, textAlign: "center" }}>{error}</Text>
          )}

          <View style={{ marginTop: space.lg }}>
            <Button label="Verify karein" onPress={() => submit(otp)} loading={busy} disabled={otp.length !== 6} />
          </View>

          <View style={{ marginTop: space.sm }}>
            <Button
              variant="ghost"
              label={wait > 0 ? `Dobara OTP ${wait} second me` : "Dobara OTP bhejein"}
              onPress={resend}
              disabled={wait > 0 || busy}
            />
            <Button variant="ghost" label="Number badlein" onPress={() => router.replace("/login")} disabled={busy} />
          </View>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
