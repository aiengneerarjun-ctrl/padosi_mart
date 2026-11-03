import { ActivityIndicator, Pressable, Text } from "react-native";
import { colors, radius, type } from "../theme";

type Props = {
  label: string;
  onPress: () => void;
  loading?: boolean;
  disabled?: boolean;
  variant?: "primary" | "ghost";
};

export function Button({ label, onPress, loading, disabled, variant = "primary" }: Props) {
  const off = disabled || loading;
  const primary = variant === "primary";
  return (
    <Pressable
      onPress={onPress}
      disabled={off}
      style={({ pressed }) => ({
        backgroundColor: primary ? colors.marigold : "transparent",
        opacity: off ? 0.45 : pressed ? 0.85 : 1,
        paddingVertical: 15,
        borderRadius: radius.pill,
        alignItems: "center",
        justifyContent: "center",
      })}
    >
      {loading ? (
        <ActivityIndicator color={colors.onMarigold} />
      ) : (
        <Text style={{ ...type.heading, color: primary ? colors.onMarigold : colors.ink }}>{label}</Text>
      )}
    </Pressable>
  );
}