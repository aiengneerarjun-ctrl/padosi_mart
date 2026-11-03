import { useEffect, useRef, useState } from "react";
import { ActivityIndicator, Alert, Linking, Pressable, Text, View } from "react-native";
import { WebView } from "react-native-webview";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { ApiError, errorMessage } from "../../src/api/client";
import { getOrder, PaymentSession, startPayment } from "../../src/api/orders";
import { IconButton } from "../../src/components/IconButton";
import { formatPrice } from "../../src/lib/media";
import { colors, radius, space, type } from "../../src/theme";

// Cashfree ka web checkout: session id se payment page khulta hai
function checkoutHtml(sessionId: string, env: string) {
  const mode = env === "production" ? "production" : "sandbox";
  return `<!DOCTYPE html><html><head>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<style>body{font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;color:#5B6D6A}</style>
</head><body>Payment page khul raha hai...
<script src="https://sdk.cashfree.com/js/v3/cashfree.js"></script>
<script>
  window.onload = function () {
    var cashfree = Cashfree({ mode: ${JSON.stringify(mode)} });
    cashfree.checkout({ paymentSessionId: ${JSON.stringify(sessionId)}, redirectTarget: "_self" });
  };
</script></body></html>`;
}

type Result = "paid" | "failed" | null;

export default function PayScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const insets = useSafeAreaInsets();

  const [session, setSession] = useState<PaymentSession | null>(null);
  const [error, setError] = useState("");
  const [result, setResult] = useState<Result>(null);
  const [pageLoading, setPageLoading] = useState(true);
  const resultRef = useRef<Result>(null);
  resultRef.current = result;

  // 1. Payment session lo
  useEffect(() => {
    if (!id) return;
    (async () => {
      try {
        setSession(await startPayment(id));
      } catch (e) {
        if (e instanceof ApiError && e.code === "PAYMENT_ALREADY_PAID") setResult("paid");
        else setError(errorMessage(e));
      }
    })();
  }, [id]);

  // 2. Backend ko Cashfree ka webhook mile, tab tak order poochte raho
  useEffect(() => {
    if (!id || result) return;
    const t = setInterval(async () => {
      try {
        const o = await getOrder(id);
        if (o.payment_status === "PAID") setResult("paid");
        else if (o.status === "CANCELLED" || o.status === "PAYMENT_FAILED") setResult("failed");
      } catch {
        // network ki chhoti dikkat: agle round me dobara
      }
    }, 3000);
    return () => clearInterval(t);
  }, [id, result]);

  // Payment ho gayi to thodi der baad order page par wapas
  useEffect(() => {
    if (result !== "paid") return;
    const t = setTimeout(() => (router.canGoBack() ? router.back() : router.replace("/")), 1800);
    return () => clearTimeout(t);
  }, [result, router]);

  const leave = () => {
    if (result) return (router.canGoBack() ? router.back() : router.replace("/"));
    Alert.alert(
      "Payment beech me chhodein?",
      "Aap order ke page se 'Abhi payment karein' dabakar baad me bhi payment kar sakte hain.",
      [
        { text: "Nahi", style: "cancel" },
        { text: "Haan, wapas jaayein", onPress: () => (router.canGoBack() ? router.back() : router.replace("/")) },
      ],
    );
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
      <IconButton name="arrow-back" onPress={leave} />
      <View style={{ marginLeft: space.md }}>
        <Text style={{ ...type.title, color: colors.onInk }}>Payment</Text>
        {session && <Text style={{ ...type.caption, color: "#B9D3CF" }}>{formatPrice(session.amount)}</Text>}
      </View>
    </View>
  );

  if (result) {
    const ok = result === "paid";
    return (
      <View style={{ flex: 1, backgroundColor: colors.canvas }}>
        {topBar}
        <View style={{ flex: 1, alignItems: "center", justifyContent: "center", padding: space.xl }}>
          <Text style={{ ...type.display, color: ok ? colors.success : colors.danger, textAlign: "center" }}>
            {ok ? "Payment ho gayi" : "Payment nahi hui"}
          </Text>
          <Text style={{ ...type.body, color: colors.textMuted, marginTop: space.sm, textAlign: "center" }}>
            {ok ? "Dhanyavaad! Aapka order dukaan tak bhej diya gaya hai." : "Order cancel ho gaya hai. Aap naya order kar sakte hain."}
          </Text>
          <Pressable
            onPress={() => (router.canGoBack() ? router.back() : router.replace("/"))}
            style={{
              marginTop: space.xl,
              backgroundColor: colors.marigold,
              paddingVertical: 14,
              paddingHorizontal: space.xl,
              borderRadius: radius.pill,
            }}
          >
            <Text style={{ ...type.heading, color: colors.onMarigold }}>Order dekhein</Text>
          </Pressable>
        </View>
      </View>
    );
  }

  if (error) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.canvas }}>
        {topBar}
        <View style={{ flex: 1, alignItems: "center", justifyContent: "center", padding: space.xl }}>
          <Text style={{ ...type.body, color: colors.danger, textAlign: "center" }}>{error}</Text>
          <Pressable onPress={() => (router.canGoBack() ? router.back() : router.replace("/"))} style={{ marginTop: space.lg }}>
            <Text style={{ ...type.heading, color: colors.ink }}>Wapas jaayein</Text>
          </Pressable>
        </View>
      </View>
    );
  }

  if (!session) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.canvas }}>
        {topBar}
        <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
          <ActivityIndicator color={colors.ink} />
        </View>
      </View>
    );
  }

  return (
    <View style={{ flex: 1, backgroundColor: colors.canvas }}>
      {topBar}
      <View style={{ flex: 1 }}>
        <WebView
          originWhitelist={["*"]}
          source={{ html: checkoutHtml(session.payment_session_id, session.environment) }}
          javaScriptEnabled
          domStorageEnabled
          thirdPartyCookiesEnabled
          setSupportMultipleWindows={false}
          onLoadEnd={() => setPageLoading(false)}
          // UPI app jaise (upi://, intent://) links ko phone ki app me kholo
          onShouldStartLoadWithRequest={(req) => {
            if (/^(https?:|about:|data:|blob:)/i.test(req.url)) return true;
            Linking.openURL(req.url).catch(() => Alert.alert("Payment", "Ye app khul nahi payi."));
            return false;
          }}
        />
        {pageLoading && (
          <View
            pointerEvents="none"
            style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0, alignItems: "center", justifyContent: "center" }}
          >
            <ActivityIndicator color={colors.ink} />
          </View>
        )}
      </View>
      <Text
        style={{
          ...type.caption,
          color: colors.textMuted,
          textAlign: "center",
          padding: space.sm,
          paddingBottom: insets.bottom + space.sm,
        }}
      >
        Payment poori hote hi ye screen khud band ho jayegi.
      </Text>
    </View>
  );
}