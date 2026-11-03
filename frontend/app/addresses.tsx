import { useCallback, useState } from "react";
import { ActivityIndicator, Alert, Pressable, ScrollView, Text, View } from "react-native";
import { useFocusEffect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Address, deleteAddress, listAddresses, makeDefaultAddress } from "../src/api/address";
import { errorMessage } from "../src/api/client";
import { Button } from "../src/components/Button";
import { IconButton } from "../src/components/IconButton";
import { colors, radius, space, type } from "../src/theme";

const LABEL_TEXT: Record<string, string> = { HOME: "Ghar", WORK: "Office", OTHER: "Doosra" };

export default function Addresses() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [items, setItems] = useState<Address[] | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      setItems(await listAddresses());
    } catch (e) {
      setError(errorMessage(e));
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  const choose = async (a: Address) => {
    if (a.is_default) return (router.canGoBack() ? router.back() : router.replace("/"));
    try {
      await makeDefaultAddress(a.id);
      (router.canGoBack() ? router.back() : router.replace("/"));
    } catch (e) {
      Alert.alert("Address", errorMessage(e));
    }
  };

  const remove = (a: Address) =>
    Alert.alert("Address hatayein?", a.address_line, [
      { text: "Nahi", style: "cancel" },
      {
        text: "Haan, hatayein",
        style: "destructive",
        onPress: async () => {
          try {
            await deleteAddress(a.id);
            await load();
          } catch (e) {
            Alert.alert("Address", errorMessage(e));
          }
        },
      },
    ]);

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
        <Text style={{ ...type.title, color: colors.onInk, marginLeft: space.md }}>Delivery address</Text>
      </View>

      {error ? (
        <View style={{ flex: 1, alignItems: "center", justifyContent: "center", padding: space.xl }}>
          <Text style={{ ...type.body, color: colors.danger, textAlign: "center" }}>{error}</Text>
          <Pressable onPress={load} style={{ marginTop: space.lg }}>
            <Text style={{ ...type.heading, color: colors.ink }}>Dobara try karein</Text>
          </Pressable>
        </View>
      ) : items === null ? (
        <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
          <ActivityIndicator color={colors.ink} />
        </View>
      ) : (
        <ScrollView contentContainerStyle={{ padding: space.lg, paddingBottom: insets.bottom + space.xxl }}>
          {items.length === 0 && (
            <Text style={{ ...type.body, color: colors.textMuted, marginBottom: space.lg }}>
              Abhi koi address nahi hai. Pehle ek address jodein.
            </Text>
          )}

          {items.map((a) => (
            <Pressable
              key={a.id}
              onPress={() => choose(a)}
              style={({ pressed }) => ({
                backgroundColor: colors.surface,
                borderWidth: a.is_default ? 2 : 1,
                borderColor: a.is_default ? colors.ink : colors.line,
                borderRadius: radius.md,
                padding: space.lg,
                marginBottom: space.md,
                opacity: pressed ? 0.92 : 1,
              })}
            >
              <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
                <View style={{ flexDirection: "row", alignItems: "center" }}>
                  <Text style={{ ...type.heading, color: colors.text }}>{LABEL_TEXT[a.label] ?? a.label}</Text>
                  {a.is_default && (
                    <View
                      style={{
                        marginLeft: space.sm,
                        backgroundColor: "#D9EBE8",
                        borderRadius: radius.pill,
                        paddingHorizontal: space.sm,
                        paddingVertical: 2,
                      }}
                    >
                      <Text style={{ ...type.caption, color: colors.inkSoft }}>Default</Text>
                    </View>
                  )}
                </View>
                <Pressable onPress={() => remove(a)} hitSlop={10}>
                  <Text style={{ ...type.caption, color: colors.danger }}>Hatayein</Text>
                </Pressable>
              </View>
              <Text style={{ ...type.body, color: colors.text, marginTop: space.xs }}>
                {a.receiver_name} · {a.receiver_phone}
              </Text>
              <Text style={{ ...type.body, color: colors.textMuted }}>{a.address_line}</Text>
              {!!a.landmark && <Text style={{ ...type.caption, color: colors.textMuted }}>Landmark: {a.landmark}</Text>}
            </Pressable>
          ))}

          <View style={{ marginTop: space.md }}>
            <Button label="Naya address jodein" onPress={() => router.push("/address-new")} />
          </View>
        </ScrollView>
      )}
    </View>
  );
}