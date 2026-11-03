import { Text, View } from "react-native";
import { statusLabel, statusTone, TONE_COLORS } from "../lib/orderUi";
import { radius, space, type } from "../theme";

export function StatusBadge({ status }: { status: string }) {
  const c = TONE_COLORS[statusTone(status)];
  return (
    <View
      style={{
        alignSelf: "flex-start",
        backgroundColor: c.bg,
        borderRadius: radius.pill,
        paddingHorizontal: space.md,
        paddingVertical: 3,
      }}
    >
      <Text style={{ ...type.caption, color: c.fg }}>{statusLabel(status)}</Text>
    </View>
  );
}