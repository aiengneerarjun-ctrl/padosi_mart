import { useState } from "react";
import { Dimensions, Image, Pressable, Text, View } from "react-native";
import { ProductCard } from "../api/shop";
import { fixMediaUrl, formatPrice } from "../lib/media";
import { colors, radius, space, type } from "../theme";
import { QtyControl } from "./QtyControl";

// Do column ki grid: screen ki chaudai me se side padding aur beech ka gap hata kar aadha
export const PRODUCT_CARD_WIDTH = (Dimensions.get("window").width - space.lg * 2 - space.md) / 2;

export function ProductCardView({ product, onPress }: { product: ProductCard; onPress?: () => void }) {
  const [failed, setFailed] = useState(false);
  const img = failed ? null : fixMediaUrl(product.image_medium_url || product.image_thumb_url);
  const hasDiscount = product.discount_percent > 0 && product.mrp > product.selling_price;

  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => ({
        width: PRODUCT_CARD_WIDTH,
        backgroundColor: colors.surface,
        borderRadius: radius.md,
        borderWidth: 1,
        borderColor: colors.line,
        overflow: "hidden",
        opacity: pressed ? 0.95 : 1,
      })}
    >
      <View style={{ width: "100%", aspectRatio: 1, backgroundColor: "#EDF2F1" }}>
        {img ? (
          <Image
            source={{ uri: img }}
            style={{ width: "100%", height: "100%" }}
            resizeMode="cover"
            onError={() => setFailed(true)}
          />
        ) : (
          <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
            <Text style={{ ...type.title, color: colors.textMuted }}>{product.name.slice(0, 1).toUpperCase()}</Text>
          </View>
        )}
        {hasDiscount && (
          <View
            style={{
              position: "absolute",
              top: space.sm,
              left: space.sm,
              backgroundColor: colors.marigold,
              borderRadius: radius.sm,
              paddingHorizontal: space.sm,
              paddingVertical: 2,
            }}
          >
            <Text style={{ ...type.caption, color: colors.onMarigold, fontFamily: type.heading.fontFamily }}>
              {product.discount_percent}% off
            </Text>
          </View>
        )}
      </View>

      <View style={{ padding: space.md }}>
        <Text numberOfLines={2} style={{ ...type.body, color: colors.text, minHeight: 44 }}>
          {product.name}
        </Text>
        <Text style={{ ...type.caption, color: colors.textMuted }}>{product.selling_unit}</Text>

        <View style={{ flexDirection: "row", alignItems: "baseline", marginTop: space.xs }}>
          <Text style={{ ...type.heading, color: colors.text }}>{formatPrice(product.selling_price)}</Text>
          {hasDiscount && (
            <Text
              style={{ ...type.caption, color: colors.textMuted, marginLeft: space.sm, textDecorationLine: "line-through" }}
            >
              {formatPrice(product.mrp)}
            </Text>
          )}
        </View>

        {product.only_left != null && (
          <Text style={{ ...type.caption, color: colors.danger }}>Sirf {product.only_left} bache hain</Text>
        )}
        <Text numberOfLines={1} style={{ ...type.caption, color: colors.textMuted, marginTop: 2 }}>
          {product.store.name} · {product.eta_minutes} min
        </Text>

        <View style={{ marginTop: space.md }}>
          <QtyControl productId={product.id} />
        </View>
      </View>
    </Pressable>
  );
}
