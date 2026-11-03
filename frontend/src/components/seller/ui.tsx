import { ReactNode } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  TextInputProps,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { colors, radius, shadow, space, type } from "../../theme";

// ---------- Header: hara patti, peeche jaane ka button, title ----------
export function SellerHeader({
  title,
  subtitle,
  onBack,
  right,
}: {
  title: string;
  subtitle?: string;
  onBack?: () => void;
  right?: ReactNode;
}) {
  const insets = useSafeAreaInsets();
  return (
    <View
      style={{
        backgroundColor: colors.ink,
        paddingTop: insets.top + space.md,
        paddingHorizontal: space.lg,
        paddingBottom: space.lg,
      }}
    >
      <View style={{ flexDirection: "row", alignItems: "center" }}>
        {onBack && (
          <Pressable onPress={onBack} hitSlop={12} style={{ marginRight: space.md }}>
            <Ionicons name="arrow-back" size={24} color={colors.onInk} />
          </Pressable>
        )}
        <View style={{ flex: 1 }}>
          <Text style={{ ...type.title, color: colors.onInk }} numberOfLines={1}>
            {title}
          </Text>
          {!!subtitle && (
            <Text style={{ ...type.caption, color: "#B9D3CF" }} numberOfLines={1}>
              {subtitle}
            </Text>
          )}
        </View>
        {right}
      </View>
    </View>
  );
}

// ---------- Safed card ----------
export function Card({ children, style }: { children: ReactNode; style?: object }) {
  return (
    <View
      style={{
        backgroundColor: colors.surface,
        borderWidth: 1,
        borderColor: colors.line,
        borderRadius: radius.md,
        padding: space.lg,
        ...style,
      }}
    >
      {children}
    </View>
  );
}

// ---------- Ek line: baayen label, daayen value ----------
export function KV({ k, v, bold, color }: { k: string; v: string; bold?: boolean; color?: string }) {
  return (
    <View style={{ flexDirection: "row", justifyContent: "space-between", paddingVertical: 4 }}>
      <Text style={{ ...type.body, color: colors.textMuted, flex: 1 }}>{k}</Text>
      <Text style={{ ...(bold ? type.heading : type.body), color: color ?? colors.text, marginLeft: space.md }}>{v}</Text>
    </View>
  );
}

// ---------- Chhota rangeen label ----------
export type BadgeTone = "progress" | "good" | "bad" | "neutral";
const TONES: Record<BadgeTone, { bg: string; fg: string }> = {
  progress: { bg: "#FCE9C2", fg: "#C98A00" },
  good: { bg: "#DDF1E4", fg: "#1F8A4C" },
  bad: { bg: "#F7DAD7", fg: "#C8372D" },
  neutral: { bg: "#E8EEEC", fg: "#5B6D6A" },
};
export function Badge({ label, tone = "neutral" }: { label: string; tone?: BadgeTone }) {
  const c = TONES[tone];
  return (
    <View
      style={{
        alignSelf: "flex-start",
        backgroundColor: c.bg,
        borderRadius: radius.pill,
        paddingHorizontal: space.md,
        paddingVertical: 2,
      }}
    >
      <Text style={{ ...type.caption, color: c.fg }}>{label}</Text>
    </View>
  );
}

// ---------- Label ke saath text input ----------
type FieldProps = TextInputProps & {
  label: string;
  hint?: string;
  error?: string;
  prefix?: string;
};
export function Field({ label, hint, error, prefix, style, ...rest }: FieldProps) {
  return (
    <View style={{ marginTop: space.lg }}>
      <Text style={{ ...type.caption, color: colors.textMuted, marginBottom: 4 }}>{label}</Text>
      <View
        style={{
          flexDirection: "row",
          alignItems: "center",
          backgroundColor: colors.surface,
          borderWidth: 1.5,
          borderColor: error ? colors.danger : colors.line,
          borderRadius: radius.md,
          paddingHorizontal: space.lg,
        }}
      >
        {!!prefix && <Text style={{ ...type.body, color: colors.textMuted, marginRight: space.sm }}>{prefix}</Text>}
        <TextInput
          placeholderTextColor={colors.textMuted}
          {...rest}
          style={[
            { ...type.body, flex: 1, color: colors.text, paddingVertical: 12 },
            rest.multiline ? { minHeight: 80, textAlignVertical: "top" } : null,
            style,
          ]}
        />
      </View>
      {!!hint && !error && <Text style={{ ...type.caption, color: colors.textMuted, marginTop: 4 }}>{hint}</Text>}
      {!!error && <Text style={{ ...type.caption, color: colors.danger, marginTop: 4 }}>{error}</Text>}
    </View>
  );
}

// ---------- Ek chun lo wale gol chips ----------
export type ChipOption<T extends string | number> = { value: T; label: string; count?: number };
export function Chips<T extends string | number>({
  options,
  value,
  onChange,
  wrap,
}: {
  options: ChipOption<T>[];
  value: T;
  onChange: (v: T) => void;
  wrap?: boolean;
}) {
  const items = options.map((o) => {
    const on = o.value === value;
    return (
      <Pressable
        key={String(o.value)}
        onPress={() => onChange(o.value)}
        style={{
          backgroundColor: on ? colors.ink : colors.surface,
          borderWidth: 1,
          borderColor: on ? colors.ink : colors.line,
          borderRadius: radius.pill,
          paddingHorizontal: space.lg,
          paddingVertical: 7,
          marginRight: space.sm,
          marginBottom: wrap ? space.sm : 0,
          flexDirection: "row",
          alignItems: "center",
        }}
      >
        <Text style={{ ...type.body, color: on ? colors.onInk : colors.text }}>{o.label}</Text>
        {!!o.count && (
          <View
            style={{
              marginLeft: 6,
              minWidth: 20,
              height: 20,
              paddingHorizontal: 5,
              borderRadius: 10,
              backgroundColor: on ? colors.marigold : "#F7DAD7",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Text style={{ ...type.caption, lineHeight: 16, color: on ? colors.onMarigold : colors.danger }}>{o.count}</Text>
          </View>
        )}
      </Pressable>
    );
  });
  if (wrap) return <View style={{ flexDirection: "row", flexWrap: "wrap" }}>{items}</View>;
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: space.lg }}>
      {items}
    </ScrollView>
  );
}

// ---------- Khali ya error screen ----------
export function EmptyState({
  title,
  body,
  action,
}: {
  title: string;
  body?: string;
  action?: ReactNode;
}) {
  return (
    <View style={{ alignItems: "center", padding: space.xxl }}>
      <Text style={{ ...type.heading, color: colors.text, textAlign: "center" }}>{title}</Text>
      {!!body && <Text style={{ ...type.body, color: colors.textMuted, textAlign: "center", marginTop: space.xs }}>{body}</Text>}
      {!!action && <View style={{ marginTop: space.lg, alignSelf: "stretch" }}>{action}</View>}
    </View>
  );
}

export function Centered({ children }: { children: ReactNode }) {
  return <View style={{ flex: 1, alignItems: "center", justifyContent: "center", padding: space.xl }}>{children}</View>;
}

export function Spinner() {
  return (
    <Centered>
      <ActivityIndicator color={colors.ink} />
    </Centered>
  );
}

export function ErrorText({ children }: { children?: string }) {
  if (!children) return null;
  return <Text style={{ ...type.caption, color: colors.danger, marginTop: space.md }}>{children}</Text>;
}

// ---------- Neeche se upar aane wali sheet ----------
export function Sheet({
  visible,
  onClose,
  title,
  children,
}: {
  visible: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}) {
  const insets = useSafeAreaInsets();
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <Pressable style={{ flex: 1, backgroundColor: "rgba(14,59,54,0.45)" }} onPress={onClose} />
        <View
          style={{
            backgroundColor: colors.surface,
            borderTopLeftRadius: radius.lg,
            borderTopRightRadius: radius.lg,
            maxHeight: "85%",
            ...shadow.raised,
          }}
        >
          <View style={{ flexDirection: "row", alignItems: "center", padding: space.lg, paddingBottom: space.sm }}>
            <Text style={{ ...type.title, color: colors.text, flex: 1 }}>{title}</Text>
            <Pressable onPress={onClose} hitSlop={12}>
              <Ionicons name="close" size={24} color={colors.textMuted} />
            </Pressable>
          </View>
          <ScrollView
            keyboardShouldPersistTaps="handled"
            contentContainerStyle={{ padding: space.lg, paddingTop: 0, paddingBottom: insets.bottom + space.xl }}
          >
            {children}
          </ScrollView>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

// ---------- Text se number nikalna (₹ ya comma ho to bhi) ----------
export function toNumber(s: string): number {
  const n = Number(s.replace(/,/g, ".").trim());
  return Number.isFinite(n) ? n : NaN;
}

// "12.50" jaisa saaf string (paise tak), galat ho to None
export function toMoney(s: string): string | null {
  const t = s.replace(/,/g, ".").trim();
  if (!/^\d+(\.\d{1,2})?$/.test(t)) return null;
  return Number(t) > 0 ? t : null;
}
