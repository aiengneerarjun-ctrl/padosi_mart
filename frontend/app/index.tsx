import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Keyboard,
  Pressable,
  RefreshControl,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { FloatingCartBar } from "../src/components/FloatingCartBar";
import { errorMessage } from "../src/api/client";
import { listProducts, nearbyStores, ProductCard, StoreCard, suggest, Suggestions } from "../src/api/shop";
import { useAuth } from "../src/auth/AuthContext";
import { ProductCardView } from "../src/components/ProductCardView";
import { StoreCardView } from "../src/components/StoreCardView";
import { useCoords } from "../src/lib/LocationContext";
import { useRouter } from "expo-router";
import { colors, radius, space, type } from "../src/theme";
import { STORE_CATEGORIES } from "../src/lib/storeCategories";
import type { StoreCategoryCode } from "../src/lib/storeCategories";

const PAGE = 20;

const FILTERS = [{ label: "Sab dukaan", value: undefined }, ...STORE_CATEGORIES.map(({ label, value }) => ({ label, value }))];

export default function Home() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { user, signOut, setMode } = useAuth();
  const coords = useCoords();

  const [storeCategory, setStoreCategory] = useState<StoreCategoryCode | undefined>(undefined);
  const [text, setText] = useState(""); // jo user type kar raha hai
  const [query, setQuery] = useState(""); // jo search ho chuka hai

  const [stores, setStores] = useState<StoreCard[]>([]);
  const [products, setProducts] = useState<ProductCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState("");
  const [sugg, setSugg] = useState<Suggestions | null>(null);

  const load = useCallback(
    async (mode: "initial" | "refresh") => {
      if (!coords) return;
      mode === "refresh" ? setRefreshing(true) : setLoading(true);
      setError("");
      const geo = { lat: coords.lat, lng: coords.lng, q: query || undefined };
      try {
        const [s, p] = await Promise.all([
          nearbyStores({ ...geo, store_category: storeCategory, limit: PAGE }),
          listProducts({ ...geo, limit: PAGE, offset: 0 }),
        ]);
        setStores(s);
        setProducts(p);
        setHasMore(p.length === PAGE);
      } catch (e) {
        setError(errorMessage(e));
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [coords, storeCategory, query],
  );

  useEffect(() => {
    load("initial");
  }, [load]);

  const loadMore = async () => {
    if (!coords || loading || loadingMore || !hasMore) return;
    setLoadingMore(true);
    try {
      const next = await listProducts({
        lat: coords.lat,
        lng: coords.lng,
        q: query || undefined,
        limit: PAGE,
        offset: products.length,
      });
      setProducts((prev) => [...prev, ...next]);
      setHasMore(next.length === PAGE);
    } catch {
      setHasMore(false);
    } finally {
      setLoadingMore(false);
    }
  };

  // Autocomplete: type rukne ke 300ms baad
  const trimmed = text.trim();
  const showSuggest = trimmed.length >= 2 && trimmed !== query;
  useEffect(() => {
    if (!coords || !showSuggest) {
      setSugg(null);
      return;
    }
    const id = setTimeout(async () => {
      try {
        setSugg(await suggest({ lat: coords.lat, lng: coords.lng, q: trimmed }));
      } catch {
        setSugg(null);
      }
    }, 300);
    return () => clearTimeout(id);
  }, [trimmed, coords, showSuggest]);

  const runSearch = (q: string) => {
    setText(q);
    setQuery(q.trim());
    setSugg(null);
    Keyboard.dismiss();
  };
  const clearSearch = () => {
    setText("");
    setQuery("");
    setSugg(null);
  };

  const listHeader = (
    <View>
      {query ? (
        <Text style={{ ...type.body, color: colors.textMuted, marginBottom: space.md }}>
          “{query}” ke nateeje
        </Text>
      ) : null}

      <Text style={{ ...type.heading, color: colors.text, marginBottom: space.md }}>Paas ki dukaanein</Text>
      {stores.length === 0 && !loading ? (
        <Text style={{ ...type.body, color: colors.textMuted, marginBottom: space.lg }}>
          Is jagah abhi koi khuli dukaan nahi mili.
          {coords
            ? ` Aapki location: ${coords.lat}, ${coords.lng} (${coords.source === "device" ? "GPS" : "default Barharia, GPS ki ijazat nahi mili"}). Dukaan tabhi dikhegi jab aap uske delivery daayre ke andar ho.`
            : ""}
        </Text>
      ) : (
        <FlatList
          horizontal
          data={stores}
          keyExtractor={(s) => s.id}
          showsHorizontalScrollIndicator={false}
          ItemSeparatorComponent={() => <View style={{ width: space.md }} />}
          renderItem={({ item }) => (
            <StoreCardView
              store={item}
              onPress={() => router.push({ pathname: "/store/[id]", params: { id: item.id } })}
            />
          )}
          style={{ marginBottom: space.xl, marginHorizontal: -space.lg }}
          contentContainerStyle={{ paddingHorizontal: space.lg }}
        />
      )}

      <Text style={{ ...type.heading, color: colors.text, marginBottom: space.md }}>
        {query ? "Products" : "Aapke paas ke products"}
      </Text>
    </View>
  );

  return (
    <View style={{ flex: 1, backgroundColor: colors.canvas }}>
      {/* Upar ka hara hissa: greeting + search */}
      <View
        style={{
          backgroundColor: colors.ink,
          paddingTop: insets.top + space.md,
          paddingHorizontal: space.lg,
          paddingBottom: space.lg,
        }}
      >
        <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
          <View style={{ flex: 1 }}>
            <Text style={{ ...type.title, color: colors.onInk }}>
              {user?.name ? `Namaste, ${user.name}` : "Namaste"}
            </Text>
            <Text style={{ ...type.caption, color: "#B9D3CF" }}>
              {coords ? (coords.source === "device" ? "Aapki location ke paas" : "Default location (test)") : "Location dhoond rahe hain..."}
            </Text>
          </View>
          <View style={{ flexDirection: "row" }}>
            <Pressable
              onPress={async () => {
                await setMode("seller");
                router.replace("/seller");
              }}
              hitSlop={10}
              style={{ marginRight: space.lg }}
            >
              <Text style={{ ...type.body, color: colors.marigold }}>Seller</Text>
            </Pressable>
            <Pressable onPress={() => router.push("/orders")} hitSlop={10} style={{ marginRight: space.lg }}>
              <Text style={{ ...type.body, color: colors.marigold }}>Orders</Text>
            </Pressable>
            <Pressable onPress={signOut} hitSlop={10}>
              <Text style={{ ...type.body, color: colors.marigold }}>Logout</Text>
            </Pressable>
          </View>
        </View>

        <View
          style={{
            flexDirection: "row",
            alignItems: "center",
            backgroundColor: colors.surface,
            borderRadius: radius.pill,
            marginTop: space.md,
            paddingHorizontal: space.lg,
          }}
        >
          <TextInput
            value={text}
            onChangeText={setText}
            onSubmitEditing={() => trimmed && runSearch(trimmed)}
            returnKeyType="search"
            placeholder="Dukaan ya saman dhoondein"
            placeholderTextColor={colors.textMuted}
            style={{ ...type.body, flex: 1, paddingVertical: 12, color: colors.text }}
          />
          {text.length > 0 && (
            <Pressable onPress={clearSearch} hitSlop={10}>
              <Text style={{ ...type.body, color: colors.textMuted }}>Hatayein</Text>
            </Pressable>
          )}
        </View>
      </View>

      {/* Dukaan / Restaurant filter */}
      <View style={{ paddingVertical: space.md }}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: space.lg }}>
          {FILTERS.map((f) => {
            const on = storeCategory === f.value;
            return (
              <Pressable
                key={f.label}
                onPress={() => setStoreCategory(f.value)}
                style={{ backgroundColor: on ? colors.ink : colors.surface, borderWidth: 1, borderColor: on ? colors.ink : colors.line, borderRadius: radius.pill, paddingHorizontal: space.lg, paddingVertical: space.sm, marginRight: space.sm }}
              >
                <Text style={{ ...type.body, color: on ? colors.onInk : colors.text }}>{f.label}</Text>
              </Pressable>
            );
          })}
        </ScrollView>
      </View>

      {showSuggest ? (
        <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ paddingHorizontal: space.lg }}>
          <Pressable onPress={() => runSearch(trimmed)} style={{ paddingVertical: space.md }}>
            <Text style={{ ...type.body, color: colors.ink }}>“{trimmed}” search karein</Text>
          </Pressable>
          {sugg?.products.map((p) => (
            <Pressable
              key={`p-${p}`}
              onPress={() => runSearch(p)}
              style={{ paddingVertical: space.md, borderTopWidth: 1, borderTopColor: colors.line }}
            >
              <Text style={{ ...type.body, color: colors.text }}>{p}</Text>
            </Pressable>
          ))}
          {sugg?.stores.map((s) => (
            <Pressable
              key={`s-${s.id}`}
              onPress={() => runSearch(s.name)}
              style={{ paddingVertical: space.md, borderTopWidth: 1, borderTopColor: colors.line }}
            >
              <Text style={{ ...type.body, color: colors.text }}>{s.name}</Text>
              <Text style={{ ...type.caption, color: colors.textMuted }}>
                {STORE_CATEGORIES.find((category) => category.value === s.store_category)?.label || "Other"}
              </Text>
            </Pressable>
          ))}
        </ScrollView>
      ) : loading ? (
        <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
          <ActivityIndicator color={colors.ink} />
        </View>
      ) : error ? (
        <View style={{ flex: 1, alignItems: "center", justifyContent: "center", padding: space.xl }}>
          <Text style={{ ...type.body, color: colors.danger, textAlign: "center" }}>{error}</Text>
          <Pressable onPress={() => load("initial")} style={{ marginTop: space.lg }}>
            <Text style={{ ...type.heading, color: colors.ink }}>Dobara try karein</Text>
          </Pressable>
        </View>
      ) : (
        <FlatList
          data={products}
          keyExtractor={(p) => p.id}
          numColumns={2}
          columnWrapperStyle={{ justifyContent: "space-between", marginBottom: space.md }}
          ListHeaderComponent={listHeader}
          ListEmptyComponent={
            <Text style={{ ...type.body, color: colors.textMuted }}>Abhi koi product nahi mila.</Text>
          }
          ListFooterComponent={loadingMore ? <ActivityIndicator color={colors.ink} style={{ margin: space.lg }} /> : null}
          renderItem={({ item }) => (
            <ProductCardView
              product={item}
              onPress={() => router.push({ pathname: "/product/[id]", params: { id: item.id } })}
            />
          )}
          onEndReached={loadMore}
          onEndReachedThreshold={0.5}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => load("refresh")} tintColor={colors.ink} />}
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={{ paddingHorizontal: space.lg, paddingBottom: insets.bottom + 100 }}
        />
      )}
      {!showSuggest && <FloatingCartBar />}
    </View>
  );
}
