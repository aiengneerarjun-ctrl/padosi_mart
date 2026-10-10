"""3 bhasha support: English (en), Hindi (hi), Bhojpuri (bho).

Rule: backend har message ka CODE bhejta hai + us code ka message user ki bhasha me.
App code (jaise OTP_INVALID) dekh kar logic chalayegi, message sirf dikhane ke liye hai.
Nayi bhasha ya naya message jodna ho to sirf is file me MESSAGES badlo.
"""
from fastapi import Request

SUPPORTED = ("en", "hi", "bho")
DEFAULT_LANG = "en"

MESSAGES: dict[str, dict[str, str]] = {
    "OTP_SENT": {
        "en": "OTP has been sent.",
        "hi": "OTP भेज दिया गया है।",
        "bho": "OTP भेज दिहल गइल बा।",
    },
    "LOGGED_OUT": {
        "en": "You have been logged out.",
        "hi": "लॉगआउट हो गया।",
        "bho": "लॉगआउट हो गइल।",
    },
    "NOT_AUTHENTICATED": {
        "en": "Please log in.",
        "hi": "कृपया लॉगिन करें।",
        "bho": "लॉगिन करीं।",
    },
    "INVALID_TOKEN": {
        "en": "Your session has expired. Please log in again.",
        "hi": "सेशन समाप्त हो गया, कृपया दोबारा लॉगिन करें।",
        "bho": "सेशन खतम हो गइल, फेर से लॉगिन करीं।",
    },
    "INVALID_REFRESH_TOKEN": {
        "en": "Please log in again.",
        "hi": "कृपया दोबारा लॉगिन करें।",
        "bho": "फेर से लॉगिन करीं।",
    },
    "ACCOUNT_DISABLED": {
        "en": "This account is not active.",
        "hi": "यह अकाउंट सक्रिय नहीं है।",
        "bho": "ई अकाउंट चालू नइखे।",
    },
    "FORBIDDEN": {
        "en": "You do not have permission for this action.",
        "hi": "इस काम की अनुमति आपके पास नहीं है।",
        "bho": "ई काम के इजाजत रउरा लगे नइखे।",
    },
    "OTP_RATE_LIMITED": {
        "en": "Too many OTP requests. Please try again later.",
        "hi": "बहुत ज़्यादा OTP अनुरोध हुए। थोड़ी देर बाद कोशिश करें।",
        "bho": "बहुत ढेर OTP मँगावल गइल। तनी देर बाद फेर कोशिश करीं।",
    },
    "OTP_TOO_MANY_ATTEMPTS": {
        "en": "Too many wrong attempts. Please request a new OTP.",
        "hi": "बहुत ज़्यादा गलत प्रयास हुए। नया OTP मँगाएँ।",
        "bho": "बहुत ढेर गलत कोशिश भइल। नया OTP मँगाईं।",
    },
    "OTP_INVALID": {
        "en": "The OTP is wrong or has expired.",
        "hi": "OTP गलत है या समाप्त हो गया है।",
        "bho": "OTP गलत बा चाहे खतम हो गइल बा।",
    },
    "NOT_A_SELLER": {
        "en": "Please apply as a seller first.",
        "hi": "पहले सेलर के लिए आवेदन करें।",
        "bho": "पहिले सेलर खातिर आवेदन करीं।",
    },
    "SELLER_EXISTS": {
        "en": "Your seller application already exists.",
        "hi": "आपका सेलर आवेदन पहले से मौजूद है।",
        "bho": "रउरा सेलर आवेदन पहिलहीं से बा।",
    },
    "SELLER_NOT_FOUND": {
        "en": "Seller not found.",
        "hi": "सेलर नहीं मिला।",
        "bho": "सेलर ना मिलल।",
    },
    "SELLER_NOT_ACTIVE": {
        "en": "Your seller account is not active yet.",
        "hi": "आपका सेलर अकाउंट अभी सक्रिय नहीं है।",
        "bho": "रउरा सेलर अकाउंट अभी चालू नइखे।",
    },
    "STORE_NOT_FOUND": {
        "en": "Store not found.",
        "hi": "दुकान नहीं मिली।",
        "bho": "दोकान ना मिलल।",
    },
    "INVALID_STATE": {
        "en": "This action is not allowed in the current state.",
        "hi": "अभी की स्थिति में यह काम नहीं हो सकता।",
        "bho": "अभी के हालत में ई काम ना हो सकेला।",
    },
        "PRODUCT_NOT_FOUND": {
        "en": "Product not found.",
        "hi": "प्रोडक्ट नहीं मिला।",
        "bho": "प्रोडक्ट ना मिलल।",
    },
    "CATEGORY_NOT_FOUND": {
        "en": "Category not found.",
        "hi": "कैटेगरी नहीं मिली।",
        "bho": "कैटेगरी ना मिलल।",
    },
    "CATEGORY_TOO_DEEP": {
        "en": "A sub-category cannot have its own sub-category.",
        "hi": "सब-कैटेगरी के अंदर सब-कैटेगरी नहीं बन सकती।",
        "bho": "सब-कैटेगरी के भीतर सब-कैटेगरी ना बन सकेला।",
    },
    "BRAND_NOT_FOUND": {
        "en": "Brand not found.",
        "hi": "ब्रांड नहीं मिला।",
        "bho": "ब्रांड ना मिलल।",
    },
    "BRAND_EXISTS": {
        "en": "This brand already exists.",
        "hi": "यह ब्रांड पहले से मौजूद है।",
        "bho": "ई ब्रांड पहिलहीं से बा।",
    },
    "SKU_EXISTS": {
        "en": "This SKU already exists in your store.",
        "hi": "यह SKU आपकी दुकान में पहले से मौजूद है।",
        "bho": "ई SKU रउरा दोकान में पहिलहीं से बा।",
    },
    "INVALID_PRICE": {
        "en": "Selling price cannot be more than MRP.",
        "hi": "बिक्री मूल्य MRP से ज़्यादा नहीं हो सकता।",
        "bho": "बिक्री के दाम MRP से ढेर ना हो सकेला।",
    },
    "NOT_ENOUGH_STOCK": {
        "en": "Stock cannot go below zero.",
        "hi": "स्टॉक शून्य से नीचे नहीं जा सकता।",
        "bho": "स्टॉक शून्य से नीचे ना जा सकेला।",
    },
        "IMAGE_INVALID": {
        "en": "This file is not a valid image.",
        "hi": "यह फ़ाइल सही इमेज नहीं है।",
        "bho": "ई फाइल सही फोटो नइखे।",
    },
    "IMAGE_FORMAT_NOT_ALLOWED": {
        "en": "Only JPG, PNG or WebP images are allowed.",
        "hi": "सिर्फ़ JPG, PNG या WebP इमेज चलेगी।",
        "bho": "खाली JPG, PNG चाहे WebP फोटो चली।",
    },
    "IMAGE_TOO_LARGE": {
        "en": "The image is too large. Maximum size is 5 MB.",
        "hi": "इमेज बहुत बड़ी है। अधिकतम 5 MB।",
        "bho": "फोटो बहुत बड़ बा। ढेर से ढेर 5 MB।",
    },
    "IMAGE_TOO_SMALL": {
        "en": "The image is too small. Minimum 400 x 400 pixels.",
        "hi": "इमेज बहुत छोटी है। कम से कम 400 x 400 पिक्सल चाहिए।",
        "bho": "फोटो बहुत छोट बा। कम से कम 400 x 400 पिक्सल चाहीं।",
    },
    "IMAGE_DUPLICATE": {
        "en": "This image is already uploaded for this product.",
        "hi": "यह इमेज इस प्रोडक्ट के लिए पहले से अपलोड है।",
        "bho": "ई फोटो एह प्रोडक्ट खातिर पहिलहीं अपलोड बा।",
    },
    "IMAGE_LIMIT_REACHED": {
        "en": "A product can have at most 8 images.",
        "hi": "एक प्रोडक्ट में अधिकतम 8 इमेज लग सकती हैं।",
        "bho": "एक प्रोडक्ट में ढेर से ढेर 8 फोटो लग सकेला।",
    },
    "IMAGE_NOT_FOUND": {
        "en": "Image not found.",
        "hi": "इमेज नहीं मिली।",
        "bho": "फोटो ना मिलल।",
    },
    "IMAGE_ORDER_MISMATCH": {
        "en": "The list must contain every image of this product exactly once.",
        "hi": "सूची में इस प्रोडक्ट की हर इमेज एक बार होनी चाहिए।",
        "bho": "लिस्ट में एह प्रोडक्ट के हर फोटो एके बेर होखे के चाहीं।",
    },
    "PRODUCT_NEEDS_IMAGE": {
        "en": "The product needs at least one image.",
        "hi": "प्रोडक्ट में कम से कम एक इमेज ज़रूरी है।",
        "bho": "प्रोडक्ट में कम से कम एगो फोटो जरूरी बा।",
    },
    "STORAGE_UNAVAILABLE": {
        "en": "Image storage is not available right now. Please try again.",
        "hi": "इमेज स्टोरेज अभी उपलब्ध नहीं है। दोबारा कोशिश करें।",
        "bho": "फोटो स्टोरेज अभी उपलब्ध नइखे। फेर कोशिश करीं।",
    },
        "ADDRESS_NOT_FOUND": {
        "en": "Address not found.",
        "hi": "पता नहीं मिला।",
        "bho": "पता ना मिलल।",
    },
    "ADDRESS_LIMIT_REACHED": {
        "en": "You cannot add more addresses. Please remove an old one first.",
        "hi": "और पते नहीं जोड़ सकते। पहले कोई पुराना पता हटाएँ।",
        "bho": "अउर पता ना जोड़ सकीं। पहिले कवनो पुरान पता हटाईं।",
    },
    "VALIDATION_ERROR": {
        "en": "Some of the information is not valid.",
        "hi": "कुछ जानकारी सही नहीं है।",
        "bho": "कुछ जानकारी सही नइखे।",
    },
}


def resolve_lang(header: str | None) -> str:
    """Accept-Language header se bhasha chuno. Example: 'bho', 'hi-IN,hi;q=0.9,en;q=0.8'."""
    if not header:
        return DEFAULT_LANG
    candidates = []
    for index, part in enumerate(header.split(",")):
        tag, _, q = part.strip().partition(";q=")
        try:
            weight = float(q) if q else 1.0
        except ValueError:
            weight = 0.0
        candidates.append((-weight, index, tag.strip().lower().split("-")[0]))
    for _, _, lang in sorted(candidates):
        if lang in SUPPORTED:
            return lang
    return DEFAULT_LANG


def translate(code: str, lang: str, fallback: str | None = None) -> str:
    entry = MESSAGES.get(code)
    if entry is None:
        return fallback or code
    return entry.get(lang) or entry["en"]


def t(code: str, request: Request) -> str:
    """Route ke andar use karo: t('OTP_SENT', request)."""
    return translate(code, getattr(request.state, "lang", DEFAULT_LANG))

def localized(obj, lang: str, base: str = "name") -> str:
    """Category/Product ka naam user ki bhasha me. Hindi/Bhojpuri khali ho to English naam."""
    if lang in ("hi", "bho"):
        return getattr(obj, f"{base}_{lang}", None) or getattr(obj, base)
    return getattr(obj, base)