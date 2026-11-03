import { useCallback, useEffect, useRef, useState } from "react";
import { Pressable, RefreshControl, ScrollView, Switch, Text, View } from "react-native";
import { useFocusEffect, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { errorMessage } from "../../src/api/client";
import { SellerOut, setShopStatus } from "../../src/api/seller";
import { listSellerOrders } from "../../src/api/sellerOrders";
import { listReturns } from "../../src/api/sellerMoney";
import { listProducts, SellerProduct } from "../../src/api/sellerProducts";
import { useAuth } from "../../src/auth/AuthContext";
import { DiagLine, diagnoseVisibility } from "../../src/seller/diagnose";
import { Button } from "../../src/components/Button";
import { Card, EmptyState, ErrorText, Spinner } from "../../src/components/seller/ui";
import { useSeller } from "../../src/seller/SellerContext";
import { colors, radius, space, type } from "../../src/theme";
import { storeCategoryLabel } from "../../src/lib/storeCategories";

const STATUS: Record<SellerOut["status"], { label: string; bg: string; fg: string; title: string; body: string }> = {
  PENDING: {
    label: "Review me",
    bg: "#FCE9C2",
    fg: "#C98A00",
    title: "Aapki application review me hai",
    body: "Hamari team aapki jaankari dekh rahi hai. Approve hote hi aap yahan se saman bechna shuru kar paayenge.",
  },
  ACTIVE: {
    label: "Active",
    bg: "#DDF1E4",
    fg: "#1F8A4C",
    title: "Aapka seller account active hai",
    body: "Badhai ho! Ab aap apni dukaan aur saman jod sakte hain.",
  },
  REJECTED: {
    label: "Reject hui",
    bg: "#F7DAD7",
    fg: "#C8372D",
    title: "Application approve nahi hui",
    body: "Neeche wajah dekhkar jaankari theek karein aur dobara apply karein.",
  },
  SUSPENDED: {
    label: "Ruka hua",
    bg: "#F7DAD7",
    fg: "#C8372D",
    title: "Aapka seller account abhi ruka hua hai",
    body: "Zyada jaankari ke liye support se baat karein.",
  },
};

type TileProps = {
  icon: React.ComponentProps<typeof Ionicons>["name"];
  title: string;
  sub: string;
  badge?: number;
  onPress: () => void;
};

function Tile({ icon, title, sub, badge, onPress }: TileProps) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => ({
        width: "48%",
        backgroundColor: colors.surface,
        borderWidth: 1,
        borderColor: colors.line,
        borderRadius: radius.md,
        padding: space.lg,
        marginBottom: space.md,
        opacity: pressed ? 0.85 : 1,
      })}
    >
      <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
        <View
          style={{
            width: 40,
            height: 40,
            borderRadius: 12,
            backgroundColor: "#E4F0EE",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Ionicons name={icon} size={22} color={colors.ink} />
        </View>
        {!!badge && (
          <View
            style={{
              minWidth: 24,
              height: 24,
              paddingHorizontal: 6,
              borderRadius: 12,
              backgroundColor: colors.danger,
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Text style={{ ...type.caption, lineHeight: 18, color: "#fff" }}>{badge}</Text>
          </View>
        )}
      </View>
      <Text style={{ ...type.heading, color: colors.text, marginTop: space.md }}>{title}</Text>
      <Text style={{ ...type.caption, color: colors.textMuted }} numberOfLines={2}>
        {sub}
      </Text>
    </Pressable>
  );
}

export default function SellerHome() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { user, setMode, signOut } = useAuth();
  const { seller, store, setStore, loading, notSeller, error, reload } = useSeller();

  const [refreshing, setRefreshing] = useState(false);
  const [newOrders, setNewOrders] = useState(0);
  const [pendingReturns, setPendingReturns] = useState(0);
  const [products, setProducts] = useState<SellerProduct[] | null>(null);
  const [diag, setDiag] = useState<DiagLine[] | null>(null);
  const [diagBusy, setDiagBusy] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [toggleError, setToggleError] = useState("");
  const sellerStatus = useRef<SellerOut["status"] | null>(null);

  useEffect(() => {
    sellerStatus.current = seller?.status ?? null;
  }, [seller?.status]);

  // Abhi apply nahi kiya: seedha form par
  useEffect(() => {
    if (notSeller) router.replace("/seller/apply");
  }, [notSeller, router]);

  const storeId = store?.id;
  const loadCounts = useCallback(async () => {
    if (!storeId) return; // dukaan hi nahi hai (ya seller nahi) to ginti mangwane ki zarurat nahi, warna 403 aate hain
    try {
      const [orders, returns, prods] = await Promise.all([
        listSellerOrders("PLACED", 50),
        listReturns("PENDING"),
        storeId ? listProducts(storeId, undefined, 100, 0) : Promise.resolve(null),
      ]);
      setNewOrders(orders.length);
      setPendingReturns(returns.length);
      setProducts(prods);
    } catch {
      // Ginti na aaye to bhi screen chalti rahe
    }
  }, [storeId]);

  // Screen par aate hi aur wapas aane par sab taza (admin ne approve kiya ho sakta hai, naya order aaya ho sakta hai)
  useFocusEffect(
    useCallback(() => {
      reload();
      loadCounts(); // saman jodkar wapas aane par checklist bhi taza ho
      const poll = setInterval(() => {
        if (sellerStatus.current === null || sellerStatus.current === "PENDING") void reload();
      }, 5000);
      return () => clearInterval(poll);
    }, [reload, loadCounts]),
  );
  const hasStore = !!store;
  useEffect(() => {
    if (hasStore) loadCounts();
  }, [hasStore, loadCounts]);

  const onRefresh = async () => {
    setRefreshing(true);
    await reload();
    await loadCounts();
    setRefreshing(false);
  };

  const goCustomer = async () => {
    await setMode("customer");
    router.replace("/");
  };

  const goBack = async () => {
    // Root fallback must switch out of the seller-only navigation guard first.
    await setMode("customer");
    router.replace("/");
  };

  const runDiag = async () => {
    if (!store) return;
    setDiagBusy(true);
    setDiag(null);
    try {
      setDiag(await diagnoseVisibility(store));
    } catch (e) {
      setDiag([{ ok: false, text: errorMessage(e) }]);
    } finally {
      setDiagBusy(false);
    }
  };

  const toggleShop = async (open: boolean) => {
    if (!store) return;
    setToggling(true);
    setToggleError("");
    try {
      setStore(await setShopStatus(store.id, open ? "OPEN" : "CLOSED"));
    } catch (e) {
      setToggleError(errorMessage(e));
    } finally {
      setToggling(false);
    }
  };

  const s = seller ? STATUS[seller.status] : null;
  const isOpen = store?.shop_status === "OPEN";

  // Customer ko dukaan dikhne ke liye ye sab zaroori hai (backend ke niyam yahi hain)
  const checks = (() => {
    if (!store || !products) return null;
    const pending = products.filter((p) => p.status === "PENDING_APPROVAL");
    const noPhoto = products.filter((p) => p.images.length === 0 && p.status !== "INACTIVE");
    const live = products.filter((p) => p.status === "ACTIVE");
    const rows: { ok: boolean; text: string }[] = [
      { ok: products.length > 0, text: products.length ? `${products.length} saman jura hai` : "Abhi koi saman nahi jura. “Saman” me jakar jodein." },
      {
        ok: noPhoto.length === 0,
        text: noPhoto.length ? `${noPhoto.length} saman me photo nahi hai. Bina photo ke admin approve nahi karega.` : "Har saman me photo hai",
      },
      {
        ok: live.length > 0 || pending.length === 0,
        text: pending.length ? `${pending.length} saman admin ke review me hai. Approve hone par hi customer ko dikhega.` : "Koi saman review me nahi atka",
      },
      {
        ok: live.length > 0,
        text: live.length ? `${live.length} saman live hai (stock ke saath)` : "Abhi koi saman live nahi hai (approve ya stock baaki)",
      },
      { ok: isOpen, text: isOpen ? "Dukaan khuli hai" : "Dukaan band hai. Upar ka switch chalu karein." },
    ];
    return { rows, all: rows.every((r) => r.ok) };
  })();

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
        <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
          <Pressable onPress={goBack} hitSlop={10} style={{ flexDirection: "row", alignItems: "center" }}>
            <Ionicons name="arrow-back" size={18} color="#B9D3CF" />
            <Text style={{ ...type.caption, color: "#B9D3CF", marginLeft: 4 }}>Wapas</Text>
          </Pressable>
          <Pressable onPress={signOut} hitSlop={10}>
            <Text style={{ ...type.body, color: colors.marigold }}>Logout</Text>
          </Pressable>
        </View>
        <Text style={{ ...type.display, color: colors.onInk, marginTop: space.xs }}>
          {seller ? seller.business_name : "Seller"}
        </Text>
        <Text style={{ ...type.body, color: "#B9D3CF" }}>{user?.phone}</Text>
      </View>

      {loading ? (
        <Spinner />
      ) : error ? (
        <EmptyState
          title={error}
          action={<Button label="Dobara try karein" onPress={reload} variant="ghost" />}
        />
      ) : (
        seller &&
        s && (
          <ScrollView
            contentContainerStyle={{ padding: space.lg, paddingBottom: insets.bottom + space.xxl }}
            refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.ink} />}
          >
            {seller.status !== "ACTIVE" && (
              <Card>
                <View
                  style={{
                    alignSelf: "flex-start",
                    backgroundColor: s.bg,
                    borderRadius: radius.pill,
                    paddingHorizontal: space.md,
                    paddingVertical: 3,
                  }}
                >
                  <Text style={{ ...type.caption, color: s.fg }}>{s.label}</Text>
                </View>
                <Text style={{ ...type.title, color: colors.text, marginTop: space.sm }}>{s.title}</Text>
                <Text style={{ ...type.body, color: colors.textMuted, marginTop: space.xs }}>{s.body}</Text>

                {!!seller.status_reason && (
                  <View style={{ backgroundColor: "#F7DAD7", borderRadius: radius.sm, padding: space.md, marginTop: space.md }}>
                    <Text style={{ ...type.caption, color: colors.danger }}>Wajah</Text>
                    <Text style={{ ...type.body, color: colors.danger }}>{seller.status_reason}</Text>
                  </View>
                )}

                <View style={{ height: 1, backgroundColor: colors.line, marginVertical: space.lg }} />
                <Text style={{ ...type.caption, color: colors.textMuted }}>Kaam ka prakaar</Text>
                <Text style={{ ...type.heading, color: colors.text }}>
                  {storeCategoryLabel(seller.store_category)}
                </Text>
                <Text style={{ ...type.caption, color: colors.textMuted, marginTop: space.sm }}>Malik</Text>
                <Text style={{ ...type.heading, color: colors.text }}>{seller.owner_name}</Text>
              </Card>
            )}

            {seller.status === "REJECTED" && (
              <View style={{ marginTop: space.lg }}>
                <Button label="Dobara apply karein" onPress={() => router.push("/seller/apply")} />
              </View>
            )}

            {seller.status === "ACTIVE" && !store && (
              <Card>
                <Text style={{ ...type.title, color: colors.text }}>Pehle apni dukaan banayein</Text>
                <Text style={{ ...type.body, color: colors.textMuted, marginTop: space.xs }}>
                  Dukaan ka naam, pata aur delivery ka daayra bharein. Uske baad saman jod sakte hain aur orders le sakte hain.
                </Text>
                <View style={{ marginTop: space.lg }}>
                  <Button label="Dukaan banayein" onPress={() => router.push("/seller/store")} />
                </View>
              </Card>
            )}

            {seller.status === "ACTIVE" && store && (
              <>
                <Card>
                  <View style={{ flexDirection: "row", alignItems: "center" }}>
                    <View style={{ flex: 1 }}>
                      <Text style={{ ...type.heading, color: colors.text }} numberOfLines={1}>
                        {store.name}
                      </Text>
                      <Text style={{ ...type.caption, color: colors.textMuted }} numberOfLines={2}>
                        {store.address}
                      </Text>
                    </View>
                    <Pressable onPress={() => router.push("/seller/store")} hitSlop={10}>
                      <Text style={{ ...type.body, color: colors.ink }}>Badlein</Text>
                    </Pressable>
                  </View>
                  <View style={{ height: 1, backgroundColor: colors.line, marginVertical: space.md }} />
                  <View style={{ flexDirection: "row", alignItems: "center" }}>
                    <View style={{ flex: 1 }}>
                      <Text style={{ ...type.heading, color: isOpen ? colors.success : colors.textMuted }}>
                        {isOpen ? "Dukaan khuli hai" : "Dukaan band hai"}
                      </Text>
                      <Text style={{ ...type.caption, color: colors.textMuted }}>
                        {isOpen ? "Customer aapse order kar sakte hain" : "Khulne par hi customer ko dikhegi"}
                      </Text>
                    </View>
                    <Switch
                      value={isOpen}
                      onValueChange={toggleShop}
                      disabled={toggling}
                      trackColor={{ false: colors.line, true: colors.success }}
                    />
                  </View>
                  <ErrorText>{toggleError}</ErrorText>
                </Card>

                {checks && (
                  <Card style={{ marginTop: space.lg, backgroundColor: checks.all ? "#DDF1E4" : "#FFF8E5" }}>
                    <Text style={{ ...type.heading, color: checks.all ? colors.success : colors.text }}>
                      {checks.all ? "Aapki dukaan customer ko dikh rahi hai" : "Customer tak pahunchne me kuch baaki hai"}
                    </Text>
                    {checks.rows.map((r, i) => (
                      <View key={i} style={{ flexDirection: "row", marginTop: space.sm }}>
                        <Ionicons
                          name={r.ok ? "checkmark-circle" : "alert-circle"}
                          size={20}
                          color={r.ok ? colors.success : colors.marigoldDeep}
                          style={{ marginRight: space.sm, marginTop: 1 }}
                        />
                        <Text style={{ ...type.body, color: colors.text, flex: 1 }}>{r.text}</Text>
                      </View>
                    ))}
                    <Text style={{ ...type.caption, color: colors.textMuted, marginTop: space.md }}>
                      Customer tabhi dekhega jab wo aapki delivery ke daayre ({store.delivery_radius_km} km) ke andar ho.
                    </Text>
                    <View style={{ marginTop: space.md }}>
                      <Button label="Customer ke nazariye se jaanchein" onPress={runDiag} loading={diagBusy} variant="ghost" />
                    </View>
                    {diag &&
                      diag.map((r, i) => (
                        <View key={i} style={{ flexDirection: "row", marginTop: space.sm }}>
                          <Ionicons
                            name={r.ok ? "checkmark-circle" : "close-circle"}
                            size={20}
                            color={r.ok ? colors.success : colors.danger}
                            style={{ marginRight: space.sm, marginTop: 1 }}
                          />
                          <Text style={{ ...type.body, color: colors.text, flex: 1 }}>{r.text}</Text>
                        </View>
                      ))}
                  </Card>
                )}

                <View style={{ flexDirection: "row", flexWrap: "wrap", justifyContent: "space-between", marginTop: space.lg }}>
                  <Tile
                    icon="receipt-outline"
                    title="Orders"
                    sub={newOrders ? `${newOrders} naye order` : "Aaye hue orders"}
                    badge={newOrders}
                    onPress={() => router.push("/seller/orders")}
                  />
                  <Tile
                    icon="cube-outline"
                    title="Saman"
                    sub="Price, stock aur photo"
                    onPress={() => router.push("/seller/products")}
                  />
                  <Tile icon="wallet-outline" title="Kamai" sub="Bikri aur payout" onPress={() => router.push("/seller/earnings")} />
                  <Tile icon="pricetag-outline" title="Coupons" sub="Apne discount" onPress={() => router.push("/seller/coupons")} />
                  <Tile
                    icon="arrow-undo-outline"
                    title="Returns"
                    sub={pendingReturns ? `${pendingReturns} saman wapas aana hai` : "Wapas aaya saman"}
                    badge={pendingReturns}
                    onPress={() => router.push("/seller/returns")}
                  />
                  <Tile icon="star-outline" title="Reviews" sub="Customer ki rai" onPress={() => router.push("/seller/reviews")} />
                </View>
              </>
            )}

            <Pressable onPress={goCustomer} style={{ alignSelf: "center", marginTop: space.xl }} hitSlop={10}>
              <Text style={{ ...type.body, color: colors.ink }}>Customer ke roop me dekhein</Text>
            </Pressable>
          </ScrollView>
        )
      )}
    </View>
  );
}
