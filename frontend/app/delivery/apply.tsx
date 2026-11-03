import { useCallback, useEffect, useState } from "react";
import { Image, Pressable, ScrollView, Text, View } from "react-native";
import * as ImagePicker from "expo-image-picker";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { ApiError, errorMessage } from "../../src/api/client";
import { applyAsDeliveryPartner, DeliveryPartner, getDeliveryPartner, IdType, PickedPhoto, VehicleType } from "../../src/api/delivery";
import { Button } from "../../src/components/Button";
import { Badge, Card, Chips, ErrorText, Field, SellerHeader, Spinner } from "../../src/components/seller/ui";
import { useAuth } from "../../src/auth/AuthContext";
import { colors, radius, space, type } from "../../src/theme";

const VEHICLES = [
  { value: "BIKE" as const, label: "Bike" },
  { value: "SCOOTER" as const, label: "Scooter" },
  { value: "BICYCLE" as const, label: "Cycle" },
];
const IDS = [
  { value: "AADHAAR" as const, label: "Aadhaar" },
  { value: "PAN" as const, label: "PAN" },
];

async function pickPhoto(): Promise<PickedPhoto | null> {
  const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ["images"], allowsEditing: true, quality: 0.8 });
  if (result.canceled || !result.assets[0]) return null;
  const asset = result.assets[0];
  return { uri: asset.uri, name: asset.fileName, mimeType: asset.mimeType };
}

export default function DeliveryApply() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { signOut } = useAuth();
  const [partner, setPartner] = useState<DeliveryPartner | null>(null);
  const [checking, setChecking] = useState(true);
  const [name, setName] = useState("");
  const [vehicle, setVehicle] = useState<VehicleType>("BIKE");
  const [vehicleNumber, setVehicleNumber] = useState("");
  const [idType, setIdType] = useState<IdType>("AADHAAR");
  const [idPhoto, setIdPhoto] = useState<PickedPhoto | null>(null);
  const [licencePhoto, setLicencePhoto] = useState<PickedPhoto | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const loadPartner = useCallback(async () => {
    setChecking(true);
    try {
      const p = await getDeliveryPartner();
      setPartner(p);
      if (p.status === "ACTIVE") router.replace("/delivery");
      if (!name) setName(p.full_name);
      setVehicle(p.vehicle_type);
      setVehicleNumber(p.vehicle_number ?? "");
      setIdType(p.id_type);
    } catch (e) {
      if (!(e instanceof ApiError && e.code === "NOT_A_PARTNER")) setError(errorMessage(e));
    } finally {
      setChecking(false);
    }
  }, [name, router]);

  useEffect(() => {
    void loadPartner();
  }, [loadPartner]);

  const choosePhoto = async (kind: "id" | "licence") => {
    try {
      const photo = await pickPhoto();
      if (kind === "id") setIdPhoto(photo);
      else setLicencePhoto(photo);
    } catch {
      setError("Gallery nahi khul payi. Photo ki ijazat dekhein.");
    }
  };

  const submit = async () => {
    if (!idPhoto) return setError("Aadhaar ya PAN ki saaf photo chunein.");
    setSaving(true);
    setError("");
    try {
      const p = await applyAsDeliveryPartner({
        full_name: name.trim(),
        vehicle_type: vehicle,
        vehicle_number: vehicleNumber.trim(),
        id_type: idType,
        id_photo: idPhoto,
        licence_photo: licencePhoto,
      });
      setPartner(p);
      setIdPhoto(null);
      setLicencePhoto(null);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  const canReapply = !partner || partner.status === "REJECTED";
  const needsVehicleNumber = vehicle !== "BICYCLE";
  const valid = name.trim().length >= 2 && (!needsVehicleNumber || vehicleNumber.trim().length >= 5) && !!idPhoto;

  return (
    <View style={{ flex: 1, backgroundColor: colors.canvas }}>
      <SellerHeader title="Delivery partner" subtitle="Aapka delivery account" />
      {checking ? (
        <Spinner />
      ) : partner && partner.status !== "REJECTED" ? (
        <ScrollView contentContainerStyle={{ padding: space.lg, paddingBottom: insets.bottom + space.xxl }}>
          <Card>
            <Badge label={partner.status === "PENDING" ? "Application review me" : "Account band hai"} tone={partner.status === "PENDING" ? "progress" : "bad"} />
            <Text style={{ ...type.title, color: colors.text, marginTop: space.md }}>
              {partner.status === "PENDING" ? "Approval ka intezaar karein" : "Account active nahi hai"}
            </Text>
            <Text style={{ ...type.body, color: colors.textMuted, marginTop: space.xs }}>
              {partner.status === "PENDING"
                ? "Aapki details admin review kar raha hai. Approval milne ke baad aap online hokar orders le sakte hain."
                : partner.status_reason || "Support se sampark karein."}
            </Text>
            <View style={{ marginTop: space.md }}>
              <Button label="Status dobara dekhein" onPress={loadPartner} loading={checking} variant="ghost" />
            </View>
          </Card>
          <View style={{ marginTop: space.md }}>
            <Button label="Logout" onPress={signOut} variant="ghost" />
          </View>
        </ScrollView>
      ) : (
        <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: space.lg, paddingBottom: insets.bottom + space.xxl }}>
          <Card>
            <Text style={{ ...type.title, color: colors.text }}>Delivery partner ke liye apply karein</Text>
            <Text style={{ ...type.body, color: colors.textMuted, marginTop: space.xs }}>
              Verification ke baad aapke area ke orders milenge. ID photo private verification ke liye bheji jayegi.
            </Text>
            {!!partner?.status_reason && <ErrorText>{partner.status_reason}</ErrorText>}
          </Card>
          <Field label="Poora naam" value={name} onChangeText={setName} maxLength={100} placeholder="ID par likha naam" />
          <Text style={{ ...type.caption, color: colors.textMuted, marginTop: space.lg, marginBottom: space.sm }}>Aapka vehicle</Text>
          <Chips options={VEHICLES} value={vehicle} onChange={setVehicle} wrap />
          {needsVehicleNumber && (
            <Field label="Vehicle number" value={vehicleNumber} onChangeText={setVehicleNumber} autoCapitalize="characters" maxLength={12} placeholder="Jaise BR 29 AB 1234" />
          )}
          <Text style={{ ...type.caption, color: colors.textMuted, marginTop: space.lg, marginBottom: space.sm }}>Verification ID</Text>
          <Chips options={IDS} value={idType} onChange={setIdType} wrap />
          <PhotoButton title={idPhoto ? "ID photo chuni gayi · badlein" : `${idType === "AADHAAR" ? "Aadhaar" : "PAN"} ki photo chunein *`} photo={idPhoto} onPress={() => void choosePhoto("id")} />
          <PhotoButton title={licencePhoto ? "Licence photo chuni gayi · badlein" : "Driving licence photo (optional)"} photo={licencePhoto} onPress={() => void choosePhoto("licence")} />
          {!!error && <ErrorText>{error}</ErrorText>}
          <View style={{ marginTop: space.lg }}>
            <Button label={partner ? "Dobara verification bhejein" : "Verification ke liye bhejein"} onPress={submit} loading={saving} disabled={!valid} />
          </View>
          <View style={{ marginTop: space.sm }}><Button label="Logout" onPress={signOut} variant="ghost" /></View>
        </ScrollView>
      )}
    </View>
  );
}

function PhotoButton({ title, photo, onPress }: { title: string; photo: PickedPhoto | null; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={{ marginTop: space.lg }}>
      <Card style={{ flexDirection: "row", alignItems: "center", padding: space.md }}>
        {photo ? (
          <Image source={{ uri: photo.uri }} style={{ width: 54, height: 54, borderRadius: radius.sm }} />
        ) : (
          <View style={{ width: 54, height: 54, borderRadius: radius.sm, backgroundColor: "#E4F0EE", alignItems: "center", justifyContent: "center" }}>
            <Text style={{ ...type.title, color: colors.ink }}>＋</Text>
          </View>
        )}
        <Text style={{ ...type.body, color: colors.text, marginLeft: space.md, flex: 1 }}>{title}</Text>
      </Card>
    </Pressable>
  );
}
