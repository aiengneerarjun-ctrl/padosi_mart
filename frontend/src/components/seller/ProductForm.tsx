import { ReactNode, useEffect, useMemo, useState } from "react";
import { Pressable, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Category, getCategories } from "../../api/sellerProducts";
import { colors, radius, space, type } from "../../theme";
import { Button } from "../Button";
import { Chips, ErrorText, Field, Sheet, toMoney, toNumber } from "./ui";

export type ProductFormValues = {
  name: string;
  name_hi: string;
  category_id: string;
  selling_unit: string;
  mrp: string;
  selling_price: string;
  description: string;
  initial_stock: number;
  low_stock_threshold: number;
};

type Initial = Partial<{
  name: string;
  name_hi: string | null;
  category_id: string;
  selling_unit: string;
  mrp: number;
  selling_price: number;
  description: string | null;
  low_stock_threshold: number;
}>;

const UNITS = ["1 kg", "500 g", "250 g", "1 L", "500 ml", "1 pc", "6 pcs", "1 packet"].map((u) => ({ value: u, label: u }));

// Naya saman jodne aur purana badalne, dono ka ek hi form
export function ProductForm({
  mode,
  initial,
  busy,
  error,
  submitLabel,
  extra,
  onSubmit,
}: {
  mode: "create" | "edit";
  initial?: Initial;
  busy: boolean;
  error: string;
  submitLabel: string;
  extra?: ReactNode;
  onSubmit: (v: ProductFormValues) => void;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [nameHi, setNameHi] = useState(initial?.name_hi ?? "");
  const [categoryId, setCategoryId] = useState(initial?.category_id ?? "");
  const [unit, setUnit] = useState(initial?.selling_unit ?? "");
  const [mrp, setMrp] = useState(initial?.mrp != null ? String(initial.mrp) : "");
  const [price, setPrice] = useState(initial?.selling_price != null ? String(initial.selling_price) : "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [stock, setStock] = useState("0");
  const [threshold, setThreshold] = useState(String(initial?.low_stock_threshold ?? 5));

  const [categories, setCategories] = useState<Category[]>([]);
  const [catError, setCatError] = useState("");
  const [catLoaded, setCatLoaded] = useState(false);
  const [catOpen, setCatOpen] = useState(false);

  useEffect(() => {
    getCategories()
      .then((c) => {
        setCategories(c);
        setCatLoaded(true);
      })
      .catch(() => setCatError("Category nahi aa payi. Internet dekhkar screen dobara kholein."));
  }, []);

  // Pehle badi category, uske neeche uski chhoti categories
  const ordered = useMemo(() => {
    const roots = categories.filter((c) => !c.parent_id);
    const out: { cat: Category; child: boolean }[] = [];
    for (const r of roots) {
      out.push({ cat: r, child: false });
      for (const c of categories.filter((x) => x.parent_id === r.id)) out.push({ cat: c, child: true });
    }
    // Jinka parent list me nahi mila unhe bhi dikhao
    for (const c of categories) if (c.parent_id && !out.some((o) => o.cat.id === c.id)) out.push({ cat: c, child: true });
    return out;
  }, [categories]);

  const catName = categories.find((c) => c.id === categoryId)?.name;

  const mrpOk = toMoney(mrp);
  const priceOk = toMoney(price);
  const priceTooHigh = !!mrpOk && !!priceOk && Number(priceOk) > Number(mrpOk);
  const stockN = toNumber(stock);
  const thrN = toNumber(threshold);
  const valid =
    name.trim().length >= 2 &&
    !!categoryId &&
    unit.trim().length >= 1 &&
    !!mrpOk &&
    !!priceOk &&
    !priceTooHigh &&
    Number.isInteger(thrN) &&
    thrN >= 0 &&
    (mode === "edit" || (Number.isInteger(stockN) && stockN >= 0));

  const submit = () =>
    onSubmit({
      name: name.trim(),
      name_hi: nameHi.trim(),
      category_id: categoryId,
      selling_unit: unit.trim(),
      mrp: mrpOk ?? "",
      selling_price: priceOk ?? "",
      description: description.trim(),
      initial_stock: mode === "create" ? stockN : 0,
      low_stock_threshold: thrN,
    });

  return (
    <View>
      <Field label="Saman ka naam" value={name} onChangeText={setName} maxLength={200} placeholder="Jaise Aashirvaad Atta" />
      <Field
        label="Hindi me naam (zaroori nahi)"
        value={nameHi}
        onChangeText={setNameHi}
        maxLength={200}
        placeholder="जैसे आशीर्वाद आटा"
      />

      <View style={{ marginTop: space.lg }}>
        <Text style={{ ...type.caption, color: colors.textMuted, marginBottom: 4 }}>Category</Text>
        <Pressable
          onPress={() => setCatOpen(true)}
          style={{
            flexDirection: "row",
            alignItems: "center",
            backgroundColor: colors.surface,
            borderWidth: 1.5,
            borderColor: colors.line,
            borderRadius: radius.md,
            paddingHorizontal: space.lg,
            paddingVertical: 12,
          }}
        >
          <Text style={{ ...type.body, flex: 1, color: catName ? colors.text : colors.textMuted }}>
            {catName ?? "Category chunein"}
          </Text>
          <Ionicons name="chevron-down" size={18} color={colors.textMuted} />
        </Pressable>
        <ErrorText>{catError}</ErrorText>
        {catLoaded && categories.length === 0 && (
          <View style={{ backgroundColor: "#FCE9C2", borderRadius: radius.sm, padding: space.md, marginTop: space.sm }}>
            <Text style={{ ...type.body, color: colors.text }}>
              Abhi platform par koi category nahi hai. Saman jodne ke liye admin ko pehle categories banani hongi (jaise Grocery, Khana). Admin se kahein, phir ye screen dobara kholein.
            </Text>
          </View>
        )}
      </View>

      <Text style={{ ...type.caption, color: colors.textMuted, marginTop: space.lg, marginBottom: space.sm }}>
        Kitni matra ka daam? (jaise 1 kg, 500 ml)
      </Text>
      <Chips options={UNITS} value={unit} onChange={setUnit} wrap />
      <Field label="Ya khud likhein" value={unit} onChangeText={setUnit} maxLength={50} placeholder="1 kg" />

      <View style={{ flexDirection: "row" }}>
        <View style={{ flex: 1, marginRight: space.sm }}>
          <Field label="MRP (chhapa daam)" value={mrp} onChangeText={setMrp} keyboardType="decimal-pad" prefix="₹" />
        </View>
        <View style={{ flex: 1, marginLeft: space.sm }}>
          <Field
            label="Aapka daam"
            value={price}
            onChangeText={setPrice}
            keyboardType="decimal-pad"
            prefix="₹"
            error={priceTooHigh ? "MRP se zyada nahi" : undefined}
          />
        </View>
      </View>

      {mode === "create" && (
        <Field
          label="Abhi kitna stock hai"
          value={stock}
          onChangeText={(v) => setStock(v.replace(/\D/g, ""))}
          keyboardType="number-pad"
          hint="Baad me bhi badha ya ghata sakte hain"
        />
      )}
      {mode === "create" && (
        <Field
          label="Itna bachne par chetavani"
          value={threshold}
          onChangeText={(v) => setThreshold(v.replace(/\D/g, ""))}
          keyboardType="number-pad"
          hint="Stock itna ya kam ho to “kam stock” dikhega"
        />
      )}

      <Field
        label="Jaankari (zaroori nahi)"
        value={description}
        onChangeText={setDescription}
        maxLength={2000}
        multiline
        placeholder="Brand, khaasiyat"
      />

      {extra}

      <ErrorText>{error}</ErrorText>
      <View style={{ marginTop: space.xl }}>
        <Button label={submitLabel} onPress={submit} loading={busy} disabled={!valid} />
      </View>

      <Sheet visible={catOpen} onClose={() => setCatOpen(false)} title="Category chunein">
        {ordered.length === 0 && <Text style={{ ...type.body, color: colors.textMuted }}>Abhi koi category nahi hai.</Text>}
        {ordered.map(({ cat, child }) => {
          const on = cat.id === categoryId;
          return (
            <Pressable
              key={cat.id}
              onPress={() => {
                setCategoryId(cat.id);
                setCatOpen(false);
              }}
              style={{
                paddingVertical: 12,
                paddingLeft: child ? space.xl : 0,
                flexDirection: "row",
                alignItems: "center",
                borderBottomWidth: 1,
                borderBottomColor: colors.line,
              }}
            >
              <Text style={{ ...(child ? type.body : type.heading), flex: 1, color: colors.text }}>{cat.name}</Text>
              {on && <Ionicons name="checkmark" size={20} color={colors.success} />}
            </Pressable>
          );
        })}
      </Sheet>
    </View>
  );
}
