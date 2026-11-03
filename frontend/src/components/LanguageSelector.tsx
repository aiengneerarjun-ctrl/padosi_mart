import { useEffect, useState } from "react";
import { Pressable, Text, View } from "react-native";
import { hasSavedLang, Lang, loadLang, saveLang } from "../lib/storage";
import { colors, radius, space, type } from "../theme";

const LANGUAGES: { value: Lang; label: string }[] = [
  { value: "en", label: "English" },
  { value: "hi", label: "हिंदी" },
  { value: "bho", label: "भोजपुरी" },
];

export function LanguageSelector({ dark = false }: { dark?: boolean }) {
  const [language, setLanguage] = useState<Lang>("en");
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    let active = true;
    void Promise.all([loadLang(), hasSavedLang()]).then(([saved, configured]) => {
      if (active) {
        setLanguage(saved);
        setVisible(!configured);
      }
    });
    return () => {
      active = false;
    };
  }, []);

  const choose = async (next: Lang) => {
    setLanguage(next);
    await saveLang(next);
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <View style={{ marginTop: space.md }}>
      <Text style={{ ...type.caption, color: dark ? "#B9D3CF" : colors.textMuted, marginBottom: space.xs }}>
        Language / भाषा चुनें
      </Text>
      <View style={{ flexDirection: "row" }}>
        {LANGUAGES.map((item, index) => {
          const selected = language === item.value;
          return (
            <Pressable
              key={item.value}
              accessibilityRole="button"
              accessibilityState={{ selected }}
              onPress={() => void choose(item.value)}
              style={{
                flex: 1,
                marginLeft: index ? space.sm : 0,
                borderWidth: 1,
                borderColor: selected ? colors.marigold : dark ? "#58716D" : colors.line,
                borderRadius: radius.pill,
                paddingVertical: space.sm,
                alignItems: "center",
                backgroundColor: selected ? (dark ? colors.marigold : "#FFF1CB") : dark ? "#24413D" : colors.surface,
              }}
            >
              <Text style={{ ...type.caption, color: selected ? colors.ink : dark ? colors.onInk : colors.text }}>
                {item.label}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}
