import { useCallback, useEffect, useState } from "react";
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, Switch, Text, TextInput, View } from "react-native";
import * as Location from "expo-location";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { AddressInput, AddressLabel, createAddress } from "../src/api/address";
import { errorMessage } from "../src/api/client";
import { useAuth } from "../src/auth/AuthContext";
import { Button } from "../src/components/Button";
import { IconButton } from "../src/components/IconButton";
import { useCoords } from "../src/lib/LocationContext";
import { colors, radius, space, type } from "../src/theme";

type Pin = { lat: number; lng: number; source: "gps" | "default" };

const LABELS: { value: AddressLabel; text: string }[] = [
  { value: "HOME", text: "Ghar" },
  { value: "WORK", text: "Office" },
  { value: "OTHER", text: "Doosra" },
];

function Field(props: {
  label: string;
  value: string;
  onChangeText: (v: string) => void;
  placeholder?: string;
  keyboardType?: "default" | "phone-pad";
  multiline?: boolean;
  maxLength?: number;
}) {
  return (
    <View style={{ marginBottom: space.lg }}>
      <Text style={{ ...type.caption, color: colors.textMuted, marginBottom: 4 }}>{props.label}</Text>
      <TextInput
        value={props.value}
        onChangeText={props.onChangeText}
        placeholder={props.placeholder}
        placeholderTextColor={colors.textMuted}
        keyboardType={props.keyboardType}
        multiline={props.multiline}
        maxLength={props.maxLength}
        style={{
          ...type.body,
          color: colors.text,
          backgroundColor: colors.surface,
          borderWidth: 1.5,
          borderColor: colors.line,
          borderRadius: radius.md,
          paddingHorizontal: space.lg,
          paddingVertical: 12,
          minHeight: props.multiline ? 84 : undefined,
          textAlignVertical: props.multiline ? "top" : "center",
        }}
      />
    </View>
  );
}

export default function AddressNew() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { user } = useAuth();
  const deviceCoords = useCoords();

  const [label, setLabel] = useState<AddressLabel>("HOME");
  const [name, setName] = useState(user?.name ?? "");
  const [phone, setPhone] = useState((user?.phone ?? "").replace(/[^\d+]/g, ""));
  const [line, setLine] = useState("");
  const [landmark, setLandmark] = useState("");
  const [makeDefault, setMakeDefault] = useState(true);

  const [pin, setPin] = useState<Pin | null>(null);
  const [locating, setLocating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const locate = useCallback(async () => {
    setLocating(true);
    let got: Pin | null = null;
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status === "granted") {
        const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.High });
        got = {
          lat: Number(pos.coords.latitude.toFixed(6)),
          lng: Number(pos.coords.longitude.toFixed(6)),
          source: "gps",
        };
      }
    } catch {
      // GPS nahi mila: neeche fallback
    }
    if (!got && deviceCoords) got = { lat: deviceCoords.lat, lng: deviceCoords.lng, source: "default" };
    setPin(got);
    setLocating(false);
  }, [deviceCoords]);

  useEffect(() => {
    locate();
    // sirf screen khulte waqt ek baar
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const phoneOk = /^\+?\d{10,14}$/.test(phone);
  const valid = name.trim().length >= 2 && phoneOk && line.trim().length >= 5 && !!pin;

  const save = async () => {
    if (!pin) return;
    setSaving(true);
    setError("");
    const body: AddressInput = {
      label,
      receiver_name: name.trim(),
      receiver_phone: phone,
      address_line: line.trim(),
      landmark: landmark.trim() || undefined,
      latitude: pin.lat,
      longitude: pin.lng,
      make_default: makeDefault,
    };
    try {
      await createAddress(body);
      (router.canGoBack() ? router.back() : router.replace("/"));
    } catch (e) {
      setError(errorMessage(e));
      setSaving(false);
    }
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.canvas }}>
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
        <Text style={{ ...type.title, color: colors.onInk, marginLeft: space.md }}>Naya address</Text>
      </View>

      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <ScrollView
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={{ padding: space.lg, paddingBottom: insets.bottom + space.xxl }}
        >
          {/* Ghar / Office / Doosra */}
          <View style={{ flexDirection: "row", marginBottom: space.lg }}>
            {LABELS.map((l) => {
              const on = label === l.value;
              return (
                <Pressable
                  key={l.value}
                  onPress={() => setLabel(l.value)}
                  style={{
                    backgroundColor: on ? colors.ink : colors.surface,
                    borderWidth: 1,
                    borderColor: on ? colors.ink : colors.line,
                    borderRadius: radius.pill,
                    paddingHorizontal: space.lg,
                    paddingVertical: space.sm,
                    marginRight: space.sm,
                  }}
                >
                  <Text style={{ ...type.body, color: on ? colors.onInk : colors.text }}>{l.text}</Text>
                </Pressable>
              );
            })}
          </View>

          <Field label="Saman lene wale ka naam" value={name} onChangeText={setName} placeholder="Jaise Ramesh Kumar" />
          <Field
            label="Phone number"
            value={phone}
            onChangeText={(v) => setPhone(v.replace(/[^\d+]/g, "").slice(0, 15))}
            placeholder="10 digit number"
            keyboardType="phone-pad"
          />
          {phone.length > 0 && !phoneOk && (
            <Text style={{ ...type.caption, color: colors.danger, marginTop: -space.md, marginBottom: space.lg }}>
              Phone number me 10 se 14 digit hone chahiye.
            </Text>
          )}
          <Field
            label="Pura address"
            value={line}
            onChangeText={setLine}
            placeholder="Ghar ka number, mohalla, gaon / sheher"
            multiline
            maxLength={300}
          />
          <Field label="Landmark (zaroori nahi)" value={landmark} onChangeText={setLandmark} placeholder="Jaise school ke paas" maxLength={150} />

          {/* Location */}
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
            <Text style={{ ...type.heading, color: colors.text }}>Delivery location</Text>
            <Text style={{ ...type.caption, color: pin?.source === "default" ? colors.marigoldDeep : colors.textMuted, marginTop: 2 }}>
              {locating
                ? "Location dhoond rahe hain..."
                : !pin
                  ? "Location nahi mili."
                  : pin.source === "gps"
                    ? "Aapki abhi ki location lagayi gayi hai."
                    : "GPS nahi mila, test location lagayi gayi hai."}
            </Text>
            <Pressable onPress={locate} disabled={locating} style={{ marginTop: space.sm }} hitSlop={8}>
              <Text style={{ ...type.body, color: colors.ink }}>Location dobara lein</Text>
            </Pressable>
          </View>

          <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: space.lg }}>
            <Text style={{ ...type.body, color: colors.text }}>Isko default address banayein</Text>
            <Switch
              value={makeDefault}
              onValueChange={setMakeDefault}
              trackColor={{ true: colors.inkSoft, false: colors.line }}
              thumbColor={colors.surface}
            />
          </View>

          {!!error && <Text style={{ ...type.caption, color: colors.danger, marginBottom: space.md }}>{error}</Text>}

          <Button label="Address save karein" onPress={save} loading={saving} disabled={!valid} />
        </ScrollView>
      </KeyboardAvoidingView>
    </View>
  );
}