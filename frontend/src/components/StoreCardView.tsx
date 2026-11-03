import { Image, Pressable, Text, View } from "react-native";
import { StoreCard } from "../api/shop";
import { fixMediaUrl, formatPrice } from "../lib/media";
import { storeCategoryLabel } from "../lib/storeCategories";
import { colors, radius, space, type } from "../theme";

export function StoreCardView({ store, onPress }: { store: StoreCard; onPress?: () => void }) {
  const isFood = store.store_type === "RESTAURANT";
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => ({
        width: 230,
        backgroundColor: colors.surface,
        borderRadius: radius.md,
        borderWidth: 1,
        borderColor: colors.line,
        padding: space.lg,
        opacity: pressed ? 0.9 : 1,
      })}
    >
      {store.image_medium_url ? (
        <Image source={{ uri: fixMediaUrl(store.image_medium_url) || undefined }} style={{ width: "100%", height: 112, borderRadius: radius.sm, backgroundColor: colors.canvas }} resizeMode="cover" />
      ) : (
        <View style={{ width: "100%", height: 112, borderRadius: radius.sm, backgroundColor: "#E9F0EE", alignItems: "center", justifyContent: "center" }}>
          <Text style={{ ...type.caption, color: colors.textMuted }}>Store photo</Text>
        </View>
      )}
      <View
        style={{
          alignSelf: "flex-start",
          backgroundColor: isFood ? "#FCE9C2" : "#D9EBE8",
          paddingHorizontal: space.sm,
          paddingVertical: 2,
          borderRadius: radius.pill,
        }}
      >
        <Text style={{ ...type.caption, color: isFood ? colors.marigoldDeep : colors.inkSoft }}>
          {storeCategoryLabel(store.store_category)}
        </Text>
      </View>

      <Text numberOfLines={1} style={{ ...type.heading, color: colors.text, marginTop: space.sm }}>
        {store.name}
      </Text>
      <Text numberOfLines={2} style={{ ...type.caption, color: colors.textMuted, marginTop: 2, minHeight: 36 }}>
        {store.cuisine || store.description || " "}
      </Text>

      <Text style={{ ...type.caption, color: colors.text, marginTop: space.sm }}>
        {store.distance_km.toFixed(1)} km · {store.eta_minutes} min
      </Text>
      {store.min_order_amount > 0 && (
        <Text style={{ ...type.caption, color: colors.textMuted }}>Kam se kam {formatPrice(store.min_order_amount)}</Text>
      )}
    </Pressable>
  );
}
