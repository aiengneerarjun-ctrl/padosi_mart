import { useState } from "react";
import { Image, KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { errorMessage } from "../../src/api/client";
import { applySeller, uploadSellerStoreImage } from "../../src/api/seller";
import { useAuth } from "../../src/auth/AuthContext";
import { Button } from "../../src/components/Button";
import { colors, radius, space, type } from "../../src/theme";
import { STORE_CATEGORIES } from "../../src/lib/storeCategories";
import type { StoreCategoryCode } from "../../src/lib/storeCategories";
import { Chips } from "../../src/components/seller/ui";
import { pickImages } from "../../src/seller/productUi";

export default function SellerApply() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { user, setMode } = useAuth();

  const [storeCategory, setStoreCategory] = useState<StoreCategoryCode>("GROCERY");
  const [storeImage, setStoreImage] = useState<string | null>(null);
  const [applicationCreated, setApplicationCreated] = useState(false);
  const [business, setBusiness] = useState("");
  const [owner, setOwner] = useState(user?.name ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const valid = business.trim().length >= 2 && owner.trim().length >= 2;

  const goBack = async () => {
    if (router.canGoBack()) {
      router.back();
      return;
    }
    // Seller mode me customer home protected hota hai; pehle mode badalna zaroori hai.
    await setMode("customer");
    router.replace("/");
  };

  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      if (!applicationCreated) {
        await applySeller({
          seller_type: storeCategory === "RESTAURANT" ? "RESTAURANT" : "KIRANA",
          store_category: storeCategory,
          business_name: business.trim(),
          owner_name: owner.trim(),
        });
        setApplicationCreated(true);
      }
      if (storeImage) await uploadSellerStoreImage(storeImage);
      router.replace("/seller");
    } catch (e) {
      setError(errorMessage(e));
      setBusy(false);
    }
  };

  const input = {
    ...type.body,
    color: colors.text,
    backgroundColor: colors.surface,
    borderWidth: 1.5,
    borderColor: colors.line,
    borderRadius: radius.md,
    paddingHorizontal: space.lg,
    paddingVertical: 12,
  } as const;

  return (
    <View style={{ flex: 1, backgroundColor: colors.canvas }}>
      <View
        style={{
          backgroundColor: colors.ink,
          paddingTop: insets.top + space.lg,
          paddingHorizontal: space.xl,
          paddingBottom: space.xl,
        }}
      >
        <View style={{ flexDirection: "row", alignItems: "center" }}>
          <Pressable onPress={goBack} hitSlop={12} style={{ marginRight: space.md }}>
            <Ionicons name="arrow-back" size={26} color={colors.onInk} />
          </Pressable>
          <Text style={{ ...type.display, color: colors.onInk }}>Seller banein</Text>
        </View>
        <Text style={{ ...type.body, color: "#B9D3CF", marginTop: space.xs }}>
          Apni dukaan ki category aur photo dein. Review ke baad dukaan banakar saman bechna shuru karein.
        </Text>
      </View>

      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <ScrollView
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={{ padding: space.lg, paddingBottom: insets.bottom + space.xxl }}
        >
          <Text style={{ ...type.heading, color: colors.text, marginTop: space.md }}>Dukaan ki photo</Text>
          <Text style={{ ...type.caption, color: colors.textMuted }}>Ye photo approval ke baad dukaan ke naam ke saath customer ko dikhegi.</Text>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Dukaan ki photo chunein"
            onPress={async () => {
              const [photo] = await pickImages(1);
              if (photo) setStoreImage(photo.uri);
            }}
            style={{ marginTop: space.sm, height: 150, borderWidth: 1.5, borderStyle: "dashed", borderColor: colors.ink, borderRadius: radius.md, backgroundColor: colors.surface, alignItems: "center", justifyContent: "center", overflow: "hidden" }}
          >
            {storeImage ? <Image source={{ uri: storeImage }} style={{ width: "100%", height: "100%" }} resizeMode="cover" /> : <Text style={{ ...type.heading, color: colors.ink }}>+ Dukaan ki photo chunein</Text>}
          </Pressable>
          <View style={{ marginTop: space.xs }}>
            <Button label={storeImage ? "Photo badlein" : "Gallery se photo chunein"} onPress={async () => {
              const [photo] = await pickImages(1);
              if (photo) setStoreImage(photo.uri);
            }} variant="ghost" />
          </View>

          <Text style={{ ...type.heading, color: colors.text, marginTop: space.md, marginBottom: space.xs }}>Dukaan ka type chunein</Text>
          <Text style={{ ...type.caption, color: colors.textMuted, marginBottom: space.sm }}>Kirana aur restaurant ke alawa hardware, medical, garments, mobile, footwear aur doosre types bhi hain.</Text>
          <View pointerEvents={applicationCreated ? "none" : "auto"} style={{ opacity: applicationCreated ? 0.55 : 1 }}>
            <Chips options={STORE_CATEGORIES.map(({ value, label }) => ({ value, label }))} value={storeCategory} onChange={setStoreCategory} wrap />
          </View>

          <Text style={{ ...type.caption, color: colors.textMuted, marginTop: space.lg, marginBottom: 4 }}>
            Dukaan ya business ka naam
          </Text>
          <TextInput
            editable={!applicationCreated}
            value={business}
            onChangeText={setBusiness}
            maxLength={150}
            placeholder="Jaise Sharma General Store"
            placeholderTextColor={colors.textMuted}
            style={input}
          />

          <Text style={{ ...type.caption, color: colors.textMuted, marginTop: space.lg, marginBottom: 4 }}>
            Malik ka naam
          </Text>
          <TextInput
            editable={!applicationCreated}
            value={owner}
            onChangeText={setOwner}
            maxLength={100}
            placeholder="Aapka poora naam"
            placeholderTextColor={colors.textMuted}
            style={input}
          />

          {applicationCreated && <Text style={{ ...type.caption, color: colors.textMuted, marginTop: space.sm }}>Application save ho gayi hai. Photo upload fail hua ho to photo dobara chunein aur neeche retry karein.</Text>}
          {!!error && <Text style={{ ...type.caption, color: colors.danger, marginTop: space.md }}>{error}</Text>}

          <View style={{ marginTop: space.xl }}>
            <Button label={applicationCreated ? "Photo upload karke aage badhein" : "Application bhejein"} onPress={submit} loading={busy} disabled={!applicationCreated && !valid} />
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </View>
  );
}
