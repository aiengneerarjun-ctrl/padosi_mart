import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Alert, Image, KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { errorMessage } from "../../../src/api/client";
import {
  adjustStock,
  deleteProductImage,
  getProduct,
  getStockHistory,
  reorderProductImages,
  SellerProduct,
  setProductStatus,
  StockReason,
  StockTransaction,
  updateProduct,
  uploadProductImage,
} from "../../../src/api/sellerProducts";
import { Button } from "../../../src/components/Button";
import { ProductForm, ProductFormValues } from "../../../src/components/seller/ProductForm";
import {
  Badge,
  Card,
  Chips,
  EmptyState,
  ErrorText,
  Field,
  SellerHeader,
  Sheet,
  Spinner,
  toNumber,
} from "../../../src/components/seller/ui";
import { fixMediaUrl, formatPrice } from "../../../src/lib/media";
import { formatDateTime } from "../../../src/lib/orderUi";
import { pickImages, PRODUCT_STATUS } from "../../../src/seller/productUi";
import { colors, radius, space, type } from "../../../src/theme";

const MAX_PHOTOS = 8;

const REASON_LABEL: Record<string, string> = {
  INITIAL: "Shuruaati stock",
  STOCK_IN: "Stock aaya",
  ADJUSTMENT: "Sudhaar",
  DAMAGED: "Kharab / toota",
  ORDER: "Order me gaya",
  ORDER_CANCEL: "Order cancel, wapas",
  RETURN: "Return me wapas",
};

export default function ProductDetail() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { id, notice } = useLocalSearchParams<{ id: string; notice?: string }>();

  const [product, setProduct] = useState<SellerProduct | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [msg, setMsg] = useState(notice ?? "");
  const [error, setError] = useState("");

  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [toggling, setToggling] = useState(false);

  // stock sheet
  const [stockOpen, setStockOpen] = useState(false);
  const [direction, setDirection] = useState<"in" | "out">("in");
  const [qty, setQty] = useState("");
  const [outReason, setOutReason] = useState<StockReason>("DAMAGED");
  const [note, setNote] = useState("");
  const [stockBusy, setStockBusy] = useState(false);
  const [stockError, setStockError] = useState("");

  // stock history
  const [history, setHistory] = useState<StockTransaction[] | null>(null);
  const [historyBusy, setHistoryBusy] = useState(false);

  const load = useCallback(async () => {
    setLoadError("");
    try {
      setProduct(await getProduct(id));
    } catch (e) {
      setLoadError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const addPhotos = async () => {
    if (!product) return;
    setError("");
    setMsg("");
    let picked;
    try {
      picked = await pickImages(MAX_PHOTOS - product.images.length);
    } catch {
      setError("Gallery nahi khul payi. Photo ki ijazat dekhein.");
      return;
    }
    if (!picked.length) return;
    setUploading(true);
    let latest = product;
    let failed = "";
    for (const img of picked) {
      try {
        latest = await uploadProductImage(product.id, img);
      } catch (e) {
        failed = errorMessage(e);
      }
    }
    setProduct(latest);
    if (failed) setError(failed);
    setUploading(false);
  };

  const removePhoto = (imageId: string) => {
    if (!product) return;
    Alert.alert("Photo hatayein?", "Ye photo is saman se hat jayegi.", [
      { text: "Rehne dein", style: "cancel" },
      {
        text: "Hatayein",
        style: "destructive",
        onPress: async () => {
          setError("");
          try {
            setProduct(await deleteProductImage(product.id, imageId));
          } catch (e) {
            setError(errorMessage(e));
          }
        },
      },
    ]);
  };

  const makePrimary = async (imageId: string) => {
    if (!product) return;
    setError("");
    const order = [imageId, ...product.images.map((i) => i.id).filter((x) => x !== imageId)];
    try {
      setProduct(await reorderProductImages(product.id, order));
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  const save = async (v: ProductFormValues) => {
    if (!product) return;
    setSaving(true);
    setError("");
    setMsg("");
    try {
      const updated = await updateProduct(product.id, {
        name: v.name,
        name_hi: v.name_hi || null,
        category_id: v.category_id,
        description: v.description || null,
        selling_unit: v.selling_unit,
        mrp: v.mrp,
        selling_price: v.selling_price,
      });
      setProduct(updated);
      setMsg(
        updated.status === "PENDING_APPROVAL" && product.status !== "PENDING_APPROVAL"
          ? "Save ho gaya. Naam ya jaankari badli, isliye admin dobara review karega."
          : "Badlav save ho gaya.",
      );
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  const toggleVisible = async () => {
    if (!product) return;
    setToggling(true);
    setError("");
    try {
      setProduct(await setProductStatus(product.id, product.status === "INACTIVE" ? "ACTIVE" : "INACTIVE"));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setToggling(false);
    }
  };

  const openStock = (dir: "in" | "out") => {
    setDirection(dir);
    setQty("");
    setNote("");
    setStockError("");
    setStockOpen(true);
  };

  const submitStock = async () => {
    if (!product) return;
    const n = toNumber(qty);
    if (!Number.isInteger(n) || n <= 0) {
      setStockError("Sahi matra likhein (1 ya zyada).");
      return;
    }
    if (direction === "out" && n > product.stock) {
      setStockError(`Abhi sirf ${product.stock} stock hai.`);
      return;
    }
    setStockBusy(true);
    setStockError("");
    try {
      const updated = await adjustStock(product.id, {
        change: direction === "in" ? n : -n,
        reason: direction === "in" ? "STOCK_IN" : outReason,
        note: note.trim() || null,
      });
      setProduct(updated);
      setHistory(null);
      setStockOpen(false);
    } catch (e) {
      setStockError(errorMessage(e));
    } finally {
      setStockBusy(false);
    }
  };

  const toggleHistory = async () => {
    if (!product) return;
    if (history) {
      setHistory(null);
      return;
    }
    setHistoryBusy(true);
    try {
      setHistory(await getStockHistory(product.id));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setHistoryBusy(false);
    }
  };

  if (loading) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.canvas }}>
        <SellerHeader title="Saman" onBack={() => (router.canGoBack() ? router.back() : router.replace("/seller"))} />
        <Spinner />
      </View>
    );
  }
  if (!product) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.canvas }}>
        <SellerHeader title="Saman" onBack={() => (router.canGoBack() ? router.back() : router.replace("/seller"))} />
        <EmptyState title={loadError || "Saman nahi mila"} action={<Button label="Dobara try karein" onPress={load} variant="ghost" />} />
      </View>
    );
  }

  const st = PRODUCT_STATUS[product.status];
  const canHide = product.status === "ACTIVE" || product.status === "OUT_OF_STOCK";

  return (
    <View style={{ flex: 1, backgroundColor: colors.canvas }}>
      <SellerHeader title={product.name} subtitle={`${product.selling_unit} · ${formatPrice(product.selling_price)}`} onBack={() => (router.canGoBack() ? router.back() : router.replace("/seller"))} />
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <ScrollView
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={{ padding: space.lg, paddingBottom: insets.bottom + space.xxl }}
        >
          {!!msg && (
            <View style={{ backgroundColor: "#DDF1E4", borderRadius: radius.sm, padding: space.md, marginBottom: space.md }}>
              <Text style={{ ...type.body, color: colors.success }}>{msg}</Text>
            </View>
          )}

          {!!error && (
            <View style={{ backgroundColor: "#F7DAD7", borderRadius: radius.sm, padding: space.md, marginBottom: space.md }}>
              <Text style={{ ...type.body, color: colors.danger }}>{error}</Text>
            </View>
          )}

          {/* Status */}
          <Card>
            <Badge label={st.label} tone={st.tone} />
            <Text style={{ ...type.body, color: colors.textMuted, marginTop: space.sm }}>{st.hint}</Text>
            {!!product.status_reason && (
              <View style={{ backgroundColor: "#F7DAD7", borderRadius: radius.sm, padding: space.md, marginTop: space.md }}>
                <Text style={{ ...type.caption, color: colors.danger }}>Wajah</Text>
                <Text style={{ ...type.body, color: colors.danger }}>{product.status_reason}</Text>
              </View>
            )}
            {canHide || product.status === "INACTIVE" ? (
              <View style={{ marginTop: space.md }}>
                <Button
                  label={product.status === "INACTIVE" ? "Wapas dikhayein" : "Customer se chhupayein"}
                  onPress={toggleVisible}
                  loading={toggling}
                  variant="ghost"
                />
              </View>
            ) : null}
          </Card>

          <Text style={{ ...type.heading, color: colors.text, marginTop: space.xl, marginBottom: space.sm }}>Aapke product ka commission</Text>
          <Card>
            <Text style={{ ...type.body, color: colors.text }}>
              {product.commission_mode === "FIXED"
                ? `${formatPrice(product.commission_value)} × ${product.commission_unit_quantity} ${product.commission_unit} har sale unit par`
                : `${product.commission_value}% (${product.commission_unit} ke hisaab se)`}
            </Text>
            <Text style={{ ...type.caption, color: colors.textMuted, marginTop: space.xs }}>
              Ye rate admin ne approval ke waqt set kiya hai. Payout seller ko admin manually deta hai.
            </Text>
          </Card>

          {/* Photo */}
          <Text style={{ ...type.heading, color: colors.text, marginTop: space.xl, marginBottom: space.sm }}>
            Photo ({product.images.length}/{MAX_PHOTOS})
          </Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ overflow: "visible" }}>
            {product.images.map((img, i) => {
              const uri = fixMediaUrl(img.medium_url);
              return (
                <View key={img.id} style={{ marginRight: space.md, width: 104 }}>
                  <View>
                    {uri && <Image source={{ uri }} style={{ width: 104, height: 104, borderRadius: radius.sm, backgroundColor: "#EDF2F1" }} />}
                    <Pressable
                      onPress={() => removePhoto(img.id)}
                      hitSlop={6}
                      style={{
                        position: "absolute",
                        top: 4,
                        right: 4,
                        width: 24,
                        height: 24,
                        borderRadius: 12,
                        backgroundColor: "rgba(200,55,45,0.95)",
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      <Ionicons name="trash-outline" size={14} color="#fff" />
                    </Pressable>
                  </View>
                  {i === 0 ? (
                    <Text style={{ ...type.caption, color: colors.success, marginTop: 4 }}>Mukhya photo</Text>
                  ) : (
                    <Pressable onPress={() => makePrimary(img.id)} hitSlop={6}>
                      <Text style={{ ...type.caption, color: colors.ink, marginTop: 4 }}>Mukhya banayein</Text>
                    </Pressable>
                  )}
                </View>
              );
            })}
            {product.images.length < MAX_PHOTOS && (
              <Pressable
                onPress={addPhotos}
                disabled={uploading}
                style={{
                  width: 104,
                  height: 104,
                  borderRadius: radius.sm,
                  borderWidth: 1.5,
                  borderStyle: "dashed",
                  borderColor: colors.ink,
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                {uploading ? (
                  <ActivityIndicator color={colors.ink} />
                ) : (
                  <>
                    <Ionicons name="camera-outline" size={28} color={colors.ink} />
                    <Text style={{ ...type.caption, color: colors.ink }}>Photo jodein</Text>
                  </>
                )}
              </Pressable>
            )}
          </ScrollView>
          {product.images.length === 0 && (
            <Text style={{ ...type.caption, color: colors.danger, marginTop: space.sm }}>
              Bina photo ke admin approve nahi kar sakta.
            </Text>
          )}

          {/* Stock */}
          <Text style={{ ...type.heading, color: colors.text, marginTop: space.xl, marginBottom: space.sm }}>Stock</Text>
          <Card>
            <View style={{ flexDirection: "row", alignItems: "baseline" }}>
              <Text style={{ ...type.display, color: product.stock === 0 || product.low_stock ? colors.danger : colors.text }}>
                {product.stock}
              </Text>
              <Text style={{ ...type.body, color: colors.textMuted, marginLeft: space.sm }}>
                {product.stock === 0 ? "bacha nahi" : product.low_stock ? "bache hain (kam)" : "bache hain"}
              </Text>
            </View>
            <View style={{ flexDirection: "row", marginTop: space.md }}>
              <View style={{ flex: 1, marginRight: space.sm }}>
                <Button label="Stock aaya (+)" onPress={() => openStock("in")} />
              </View>
              <View style={{ flex: 1, marginLeft: space.sm }}>
                <Button label="Kam karein (−)" onPress={() => openStock("out")} variant="ghost" disabled={product.stock === 0} />
              </View>
            </View>
            <Pressable onPress={toggleHistory} style={{ marginTop: space.md, alignSelf: "flex-start" }} hitSlop={8}>
              <Text style={{ ...type.body, color: colors.ink }}>{history ? "Itihaas chhupayein" : "Stock ka itihaas dekhein"}</Text>
            </Pressable>
            {historyBusy && <ActivityIndicator color={colors.ink} style={{ marginTop: space.md }} />}
            {history && (
              <View style={{ marginTop: space.sm }}>
                {history.length === 0 && <Text style={{ ...type.caption, color: colors.textMuted }}>Abhi koi badlav nahi.</Text>}
                {history.map((h) => (
                  <View
                    key={h.id}
                    style={{ flexDirection: "row", paddingVertical: 6, borderTopWidth: 1, borderTopColor: colors.line }}
                  >
                    <View style={{ flex: 1 }}>
                      <Text style={{ ...type.body, color: colors.text }}>{REASON_LABEL[h.reason] ?? h.reason}</Text>
                      <Text style={{ ...type.caption, color: colors.textMuted }}>
                        {formatDateTime(h.created_at)}
                        {h.note ? ` · ${h.note}` : ""}
                      </Text>
                    </View>
                    <View style={{ alignItems: "flex-end" }}>
                      <Text style={{ ...type.heading, color: h.change > 0 ? colors.success : colors.danger }}>
                        {h.change > 0 ? `+${h.change}` : h.change}
                      </Text>
                      <Text style={{ ...type.caption, color: colors.textMuted }}>bacha {h.quantity_after}</Text>
                    </View>
                  </View>
                ))}
              </View>
            )}
          </Card>

          {/* Jaankari badalna */}
          <Text style={{ ...type.heading, color: colors.text, marginTop: space.xl }}>Jaankari badlein</Text>
          <Text style={{ ...type.caption, color: colors.textMuted }}>
            Naam, category, matra ya jaankari badalne par admin dobara dekhega. Daam aur stock badalne par nahi.
          </Text>
          <ProductForm
            key={`${product.id}-${product.name}-${product.mrp}-${product.selling_price}-${product.status}`}
            mode="edit"
            initial={product}
            busy={saving}
            error=""
            submitLabel="Badlav save karein"
            onSubmit={save}
          />
        </ScrollView>
      </KeyboardAvoidingView>

      <Sheet visible={stockOpen} onClose={() => setStockOpen(false)} title={direction === "in" ? "Stock aaya" : "Stock kam karein"}>
        <Field
          label={direction === "in" ? "Kitna naya saman aaya?" : "Kitna kam karna hai?"}
          value={qty}
          onChangeText={(v) => setQty(v.replace(/\D/g, ""))}
          keyboardType="number-pad"
          autoFocus
          placeholder="0"
        />
        {direction === "out" && (
          <View style={{ marginTop: space.lg }}>
            <Text style={{ ...type.caption, color: colors.textMuted, marginBottom: space.sm }}>Kyun kam kar rahe hain?</Text>
            <Chips
              wrap
              value={outReason}
              onChange={setOutReason}
              options={[
                { value: "DAMAGED" as StockReason, label: "Kharab / toota" },
                { value: "ADJUSTMENT" as StockReason, label: "Ginti me sudhaar" },
              ]}
            />
          </View>
        )}
        <Field label="Note (zaroori nahi)" value={note} onChangeText={setNote} maxLength={300} placeholder="Jaise supplier se aaya" />
        <ErrorText>{stockError}</ErrorText>
        <View style={{ marginTop: space.xl }}>
          <Button label="Save karein" onPress={submitStock} loading={stockBusy} />
        </View>
      </Sheet>
    </View>
  );
}
