import { useState } from "react";
import { Image, KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { errorMessage } from "../../../src/api/client";
import { createProduct, PickedImage, uploadProductImage } from "../../../src/api/sellerProducts";
import { ProductForm, ProductFormValues } from "../../../src/components/seller/ProductForm";
import { SellerHeader } from "../../../src/components/seller/ui";
import { makeSku, pickImages } from "../../../src/seller/productUi";
import { useSeller } from "../../../src/seller/SellerContext";
import { colors, radius, space, type } from "../../../src/theme";

const MAX_PHOTOS = 8;

export default function NewProduct() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { store } = useSeller();

  const [photos, setPhotos] = useState<PickedImage[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const addPhotos = async () => {
    try {
      const picked = await pickImages(MAX_PHOTOS - photos.length);
      setPhotos((prev) => [...prev, ...picked].slice(0, MAX_PHOTOS));
    } catch {
      setError("Gallery nahi khul payi. Photo ki ijazat dekhein.");
    }
  };

  const submit = async (v: ProductFormValues) => {
    if (!store) return;
    setBusy(true);
    setError("");
    let productId: string;
    try {
      const p = await createProduct(store.id, {
        sku: makeSku(),
        category_id: v.category_id,
        name: v.name,
        name_hi: v.name_hi || null,
        description: v.description || null,
        selling_unit: v.selling_unit,
        mrp: v.mrp,
        selling_price: v.selling_price,
        initial_stock: v.initial_stock,
        low_stock_threshold: v.low_stock_threshold,
      });
      productId = p.id;
    } catch (e) {
      setError(errorMessage(e));
      setBusy(false);
      return;
    }

    // Saman ban gaya. Ab chuni hui photo ek ek karke chadhate hain.
    let failed = 0;
    let lastError = "";
    for (const img of photos) {
      try {
        await uploadProductImage(productId, img);
      } catch (e) {
        failed += 1;
        lastError = errorMessage(e);
      }
    }
    const notice =
      failed > 0
        ? `Saman ban gaya, par ${failed} photo nahi chadh payi: ${lastError}`
        : photos.length === 0
          ? "Saman ban gaya. Approve hone ke liye kam se kam ek photo jodein."
          : "Saman ban gaya. Ab admin review karega.";
    router.replace({ pathname: "/seller/products/[id]", params: { id: productId, notice } });
  };

  const photoPicker = (
    <View style={{ marginTop: space.xl }}>
      <Text style={{ ...type.heading, color: colors.text }}>Photo</Text>
      <Text style={{ ...type.caption, color: colors.textMuted, marginBottom: space.sm }}>
        Kam se kam 400×400, JPG / PNG / WebP, 5 MB tak. Pehli photo mukhya hogi.
      </Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        {photos.map((p, i) => (
          <View key={p.uri + i} style={{ marginRight: space.sm }}>
            <Image source={{ uri: p.uri }} style={{ width: 84, height: 84, borderRadius: radius.sm }} />
            <Pressable
              onPress={() => setPhotos((prev) => prev.filter((_, j) => j !== i))}
              hitSlop={6}
              style={{
                position: "absolute",
                top: -6,
                right: -6,
                width: 22,
                height: 22,
                borderRadius: 11,
                backgroundColor: colors.danger,
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Ionicons name="close" size={14} color="#fff" />
            </Pressable>
          </View>
        ))}
        {photos.length < MAX_PHOTOS && (
          <Pressable
            onPress={addPhotos}
            style={{
              width: 84,
              height: 84,
              borderRadius: radius.sm,
              borderWidth: 1.5,
              borderStyle: "dashed",
              borderColor: colors.ink,
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Ionicons name="camera-outline" size={26} color={colors.ink} />
            <Text style={{ ...type.caption, color: colors.ink }}>Jodein</Text>
          </Pressable>
        )}
      </ScrollView>
    </View>
  );

  return (
    <View style={{ flex: 1, backgroundColor: colors.canvas }}>
      <SellerHeader title="Naya saman" subtitle={store?.name} onBack={() => (router.canGoBack() ? router.back() : router.replace("/seller"))} />
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <ScrollView
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={{ padding: space.lg, paddingBottom: insets.bottom + space.xxl }}
        >
          <ProductForm
            mode="create"
            busy={busy}
            error={error}
            submitLabel={photos.length ? "Saman aur photo bhejein" : "Saman jodein"}
            extra={photoPicker}
            onSubmit={submit}
          />
          {busy && photos.length > 0 && (
            <Text style={{ ...type.caption, color: colors.textMuted, textAlign: "center", marginTop: space.md }}>
              Photo chadh rahi hai, thoda ruk jayein…
            </Text>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </View>
  );
}
