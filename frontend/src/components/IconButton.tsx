import { ComponentProps } from "react";
import { Pressable } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors } from "../theme";

type Props = {
  name: ComponentProps<typeof Ionicons>["name"];
  onPress: () => void;
  color?: string;
};

// Gol safed button, photo ya hare header ke upar bhi dikhta hai
export function IconButton({ name, onPress, color = colors.text }: Props) {
  return (
    <Pressable
      onPress={onPress}
      hitSlop={8}
      style={({ pressed }) => ({
        width: 40,
        height: 40,
        borderRadius: 20,
        backgroundColor: "rgba(255,255,255,0.94)",
        alignItems: "center",
        justifyContent: "center",
        opacity: pressed ? 0.8 : 1,
      })}
    >
      <Ionicons name={name} size={22} color={color} />
    </Pressable>
  );
}