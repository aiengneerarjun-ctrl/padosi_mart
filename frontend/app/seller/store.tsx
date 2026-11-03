import { useCallback, useEffect, useState } from "react";
import { Image, KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, View } from "react-native";
import { useRouter } from "expo-router";
import * as Location from "expo-location";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { errorMessage } from "../../src/api/client";
import { createStore, updateStore, uploadStoreImage } from "../../src/api/seller";
import { Button } from "../../src/components/Button";
import { Card, Chips, ErrorText, Field, SellerHeader, toNumber } from "../../src/components/seller/ui";
import { useSeller } from "../../src/seller/SellerContext";
import { colors, space, type } from "../../src/theme";
import { STORE_CATEGORIES } from "../../src/lib/storeCategories";
import type { StoreCategoryCode } from "../../src/lib/storeCategories";
import { pickImages } from "../../src/seller/productUi";
import { fixMediaUrl } from "../../src/lib/media";

const RADIUS_OPTIONS = [1, 2, 3, 5, 8, 10, 15].map((n) => ({ value: n, label: `${n} km` }));

// Dukaan banana ya badalna: naam, pata, location, delivery ka daayra, kam se kam order
export default function SellerStore() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { seller, store, setStore, loading: sellerLoading } = useSeller();
  const editing = !!store;

  const [name, setName] = useState(store?.name ?? seller?.business_name ?? "");
  const [description, setDescription] = useState(store?.description ?? "");
  const [cuisine, setCuisine] = useState(store?.cuisine ?? "");
  const [address, setAddress] = useState(store?.address ?? "");
  const [lat, setLat] = useState(store ? String(store.latitude) : "");
  const [lng, setLng] = useState(store ? String(store.longitude) : "");
  const [radiusKm, setRadiusKm] = useState<number>(store?.delivery_radius_km ?? 3);
  const [minOrder, setMinOrder] = useState(store ? String(store.min_order_amount) : "0");
  const [storeCategory, setStoreCategory] = useState<StoreCategoryCode>(store?.store_category ?? seller?.store_category ?? "GROCERY");
  const [storeImage, setStoreImage] = useState<string | null>(null);

  const [locating, setLocating] = useState(false);
  const [locError, setLocError] = useState("");
  const [manualLocation, setManualLocation] = useState(!!store);
  const [locationSource, setLocationSource] = useState<"device" | "manual" | null>(store ? "manual" : null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const isRestaurant = seller?.seller_type === "RESTAURANT";
  const categoryOptions = STORE_CATEGORIES.filter((category) => (category.value === "RESTAURANT") === isRestaurant);
  useEffect(() => {
    if (!editing && seller) setStoreCategory(seller.store_category);
  }, [editing, seller]);
  const latN = toNumber(lat);
  const lngN = toNumber(lng);
  const minN = toNumber(minOrder);
  const latOk = Number.isFinite(latN) && latN >= -90 && latN <= 90 && lat.trim() !== "";
  const lngOk = Number.isFinite(lngN) && lngN >= -180 && lngN <= 180 && lng.trim() !== "";
  const valid = name.trim().length >= 2 && address.trim().length >= 5 && latOk && lngOk && Number.isFinite(minN) && minN >= 0;
  const savedImage = store?.image_medium_url ?? seller?.store_image_medium_url ?? null;

  // Dukaan par khade hokar ye dabayein: GPS se sahi jagah mil jaati hai
  const useMyLocation = useCallback(async () => {
    setLocating(true);
    setLocError("");
    try {
      const perm = await Location.requestForegroundPermissionsAsync();
      if (perm.status !== "granted") {
        setLocError("Location ki ijazat nahi mili. Neeche latitude aur longitude haath se bhar sakte hain.");
        return;
      }
      const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.High });
      setLat(pos.coords.latitude.toFixed(6));
      setLng(pos.coords.longitude.toFixed(6));
      setLocationSource("device");
      setManualLocation(false);
    } catch {
      setLocError("Location nahi mil payi. GPS chalu karke dobara try karein, ya haath se bharein.");
    } finally {
      setLocating(false);
    }
  }, []);

  // Nayi dukaan register karte waqt phone se location khud lein; edit screen par saved pin ko na badlein.
  useEffect(() => {
    if (!sellerLoading && !editing) void useMyLocation();
  }, [editing, sellerLoading, useMyLocation]);

  useEffect(() => {
    if (!store) return;
    setLat(String(store.latitude));
    setLng(String(store.longitude));
    setManualLocation(true);
    setLocationSource("manual");
  }, [store]);

  const submit = async () => {
    setBusy(true);
    setError("");
    const body = {
      store_category: storeCategory,
      name: name.trim(),
      description: description.trim() || null,
      cuisine: isRestaurant ? cuisine.trim() || null : null,
      address: address.trim(),
      latitude: latN,
      longitude: lngN,
      delivery_radius_km: radiusKm,
      min_order_amount: minN,
    };
    try {
      let saved = editing && store ? await updateStore(store.id, body) : await createStore(body);
      setStore(saved);
      if (storeImage) {
        saved = await uploadStoreImage(saved.id, storeImage);
        setStore(saved);
      }
      (router.canGoBack() ? router.back() : router.replace("/seller"));
    } catch (e) {
      setError(errorMessage(e));
      setBusy(false);
    }
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.canvas }}>
      <SellerHeader
        title={editing ? "Dukaan badlein" : "Dukaan banayein"}
        subtitle="Customer ko yahi jaankari dikhegi"
        onBack={() => (router.canGoBack() ? router.back() : router.replace("/seller"))}
      />
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <ScrollView
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={{ padding: space.lg, paddingBottom: insets.bottom + space.xxl }}
        >
          <Field label="Dukaan ka naam" value={name} onChangeText={setName} maxLength={150} placeholder="Jaise Sharma General Store" />
          <Text style={{ ...type.heading, color: colors.text, marginTop: space.lg }}>Dukaan ki photo</Text>
          <Text style={{ ...type.caption, color: colors.textMuted }}>Photo customer ko dukaan ke naam ke saath dikhegi. JPG, PNG ya WebP chunein.</Text>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Dukaan ki photo chunein"
            onPress={async () => {
              const [photo] = await pickImages(1);
              if (photo) setStoreImage(photo.uri);
            }}
            style={{ marginTop: space.sm, height: 150, borderRadius: 16, borderWidth: 1.5, borderStyle: "dashed", borderColor: colors.ink, backgroundColor: colors.surface, alignItems: "center", justifyContent: "center", overflow: "hidden" }}
          >
            {(storeImage || savedImage) ? (
              <Image source={{ uri: storeImage || fixMediaUrl(savedImage) || undefined }} style={{ width: "100%", height: "100%" }} resizeMode="cover" />
            ) : <Text style={{ ...type.heading, color: colors.ink }}>+ Dukaan ki photo chunein</Text>}
          </Pressable>
          <View style={{ marginTop: space.xs }}>
            <Button
              label={(storeImage || savedImage) ? "Photo badlein" : "Gallery se photo chunein"}
              onPress={async () => {
                const [photo] = await pickImages(1);
                if (photo) setStoreImage(photo.uri);
              }}
              variant="ghost"
            />
          </View>
          <Text style={{ ...type.heading, color: colors.text, marginTop: space.xl, marginBottom: space.sm }}>Dukaan ki category</Text>
          <Text style={{ ...type.caption, color: colors.textMuted, marginBottom: space.sm }}>Ye category customer ko aapki dukaan dhoondhne mein madad karegi.</Text>
          <Chips
            options={categoryOptions.map(({ value, label }) => ({ value, label }))}
            value={storeCategory}
            onChange={setStoreCategory}
            wrap
          />
          <Field
            label="Chhota parichay (zaroori nahi)"
            value={description}
            onChangeText={setDescription}
            maxLength={500}
            multiline
            placeholder="Aap kya bechte hain, kab se hain"
          />
          {isRestaurant && (
            <Field label="Khane ka prakaar" value={cuisine} onChangeText={setCuisine} maxLength={100} placeholder="Jaise Litti chokha, Chinese" />
          )}
          <Field
            label="Dukaan ka pata"
            value={address}
            onChangeText={setAddress}
            maxLength={300}
            multiline
            placeholder="Mohalla, gali, landmark"
          />

          <Text style={{ ...type.heading, color: colors.text, marginTop: space.xl }}>Dukaan ki location</Text>
          <Text style={{ ...type.caption, color: colors.textMuted }}>
            Nayi dukaan ke liye phone ki current location apne aap li ja rahi hai. Dukaan par khade rahein; chahein to pin manually bhi bhar sakte hain.
          </Text>
          <View style={{ marginTop: space.md }}>
            <Button label="Meri abhi ki location dobara lein" onPress={useMyLocation} loading={locating} variant="ghost" />
          </View>
          {!!lat && !!lng && !manualLocation && (
            <Text style={{ ...type.caption, color: colors.textMuted, marginTop: space.xs }}>
              {locationSource === "device" ? "Phone ki current location set hai." : "Saved location set hai."}
            </Text>
          )}
          <View style={{ marginTop: space.xs }}>
            <Button
              label={manualLocation ? "Manual location chhupayein" : "Location manually bharna hai?"}
              onPress={() => {
                setManualLocation((value) => !value);
                setLocError("");
              }}
              variant="ghost"
            />
          </View>
          <ErrorText>{locError}</ErrorText>
          {manualLocation && <View style={{ flexDirection: "row" }}>
            <View style={{ flex: 1, marginRight: space.sm }}>
              <Field
                label="Latitude"
                value={lat}
                onChangeText={(value) => {
                  setLat(value);
                  setLocationSource("manual");
                }}
                keyboardType="numbers-and-punctuation"
                placeholder="26.319000"
                error={lat && !latOk ? "-90 se 90 ke beech" : undefined}
              />
            </View>
            <View style={{ flex: 1, marginLeft: space.sm }}>
              <Field
                label="Longitude"
                value={lng}
                onChangeText={(value) => {
                  setLng(value);
                  setLocationSource("manual");
                }}
                keyboardType="numbers-and-punctuation"
                placeholder="84.459000"
                error={lng && !lngOk ? "-180 se 180 ke beech" : undefined}
              />
            </View>
          </View>}

          <Text style={{ ...type.heading, color: colors.text, marginTop: space.xl, marginBottom: space.sm }}>
            Delivery kitni door tak?
          </Text>
          <Text style={{ ...type.caption, color: colors.textMuted, marginBottom: space.sm }}>
            Customer apni location se is daayre ke andar ho tabhi aapki dukaan dekh paayega.
          </Text>
          <Chips options={RADIUS_OPTIONS} value={radiusKm} onChange={setRadiusKm} wrap />

          <Field
            label="Kam se kam order (₹)"
            value={minOrder}
            onChangeText={setMinOrder}
            keyboardType="decimal-pad"
            prefix="₹"
            hint="0 rakhein to koi minimum nahi"
          />

          {!editing && (
            <Card style={{ marginTop: space.xl, backgroundColor: "#FFF8E5" }}>
              <Text style={{ ...type.caption, color: colors.textMuted }}>
                Nayi dukaan band se shuru hoti hai. Saman jodne ke baad dukaan ko khud “khuli” karein.
              </Text>
            </Card>
          )}

          <ErrorText>{error}</ErrorText>
          <View style={{ marginTop: space.xl }}>
            <Button label={editing ? "Badlav save karein" : "Dukaan banayein"} onPress={submit} loading={busy} disabled={!valid} />
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </View>
  );
}
