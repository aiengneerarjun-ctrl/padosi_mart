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
        "CART_STORE_TOO_FAR": {
        "en": "This shop is too far from the shops in your cart. You will need to place two separate orders, and two delivery charges will apply.",
        "hi": "यह दुकान आपके कार्ट की दुकानों से बहुत दूर है। आपको दो अलग ऑर्डर करने होंगे और दो बार डिलीवरी चार्ज लगेगा।",
        "bho": "ई दोकान रउरा कार्ट के दोकानन से बहुत दूर बा। रउरा दू अलग ऑर्डर करे के परी आ दू बेर डिलीवरी चार्ज लागी।",
    },
    "CART_STOCK_LOW": {
        "en": "That much stock is not available.",
        "hi": "इतना स्टॉक उपलब्ध नहीं है।",
        "bho": "एतना स्टॉक मौजूद नइखे।",
    },
    "CART_FULL": {
        "en": "Your cart is full. Please remove some items first.",
        "hi": "आपका कार्ट भर गया है। पहले कुछ आइटम हटाएँ।",
        "bho": "रउरा कार्ट भर गइल बा। पहिले कुछ आइटम हटाईं।",
    },
        "ADDRESS_REQUIRED": {
        "en": "Please add a delivery address first.",
        "hi": "पहले डिलीवरी का पता जोड़ें।",
        "bho": "पहिले डिलीवरी के पता जोड़ीं।",
    },
        "CART_EMPTY": {
        "en": "Your cart is empty.",
        "hi": "आपका कार्ट खाली है।",
        "bho": "रउरा कार्ट खाली बा।",
    },
    "CART_HAS_UNAVAILABLE_ITEMS": {
        "en": "Some items in your cart are not available right now. Please remove them.",
        "hi": "आपके कार्ट के कुछ आइटम अभी उपलब्ध नहीं हैं। उन्हें हटा दें।",
        "bho": "रउरा कार्ट के कुछ आइटम अभी मौजूद नइखे। ओकरा के हटा दीं।",
    },
    "PRICE_CHANGED": {
        "en": "The total has changed. Please review your cart and order again.",
        "hi": "कुल रकम बदल गई है। कार्ट दोबारा देखकर ऑर्डर करें।",
        "bho": "कुल रकम बदल गइल बा। कार्ट फेर से देखके ऑर्डर करीं।",
    },
    "ORDER_ITEMS_CHANGED": {
        "en": "Stock of some items has just reduced. Please review your cart.",
        "hi": "कुछ आइटम का स्टॉक अभी कम हो गया है। कार्ट दोबारा देखें।",
        "bho": "कुछ आइटम के स्टॉक अभी कम हो गइल बा। कार्ट फेर से देखीं।",
    },
    "PAYMENT_METHOD_NOT_AVAILABLE": {
        "en": "This payment method is not available yet.",
        "hi": "यह भुगतान तरीका अभी उपलब्ध नहीं है।",
        "bho": "ई भुगतान के तरीका अभी मौजूद नइखे।",
    },
    "ORDER_NOT_FOUND": {
        "en": "Order not found.",
        "hi": "ऑर्डर नहीं मिला।",
        "bho": "ऑर्डर ना मिलल।",
    },
    "ORDER_CANNOT_CANCEL": {
        "en": "This order can no longer be cancelled.",
        "hi": "अब यह ऑर्डर रद्द नहीं हो सकता।",
        "bho": "अब ई ऑर्डर रद्द ना हो सकेला।",
    },
        "ORDER_ITEM_NOT_FOUND": {
        "en": "This item is not part of this order.",
        "hi": "यह आइटम इस ऑर्डर में नहीं है।",
        "bho": "ई सामान एह ऑर्डर में नइखे।",
    },
    "REMOVAL_NOTE_REQUIRED": {
        "en": "Please write the reason when you choose Other.",
        "hi": "'अन्य' चुनने पर कारण लिखना ज़रूरी है।",
        "bho": "'दोसर' चुनला पर कारण लिखल जरूरी बा।",
    },
    "REMOVAL_REASON_OUT_OF_STOCK": {
        "en": "Not available at the shop right now",
        "hi": "दुकान में अभी उपलब्ध नहीं है",
        "bho": "दोकान में अभी उपलब्ध नइखे",
    },
    "REMOVAL_REASON_QUALITY_ISSUE": {
        "en": "Not in good condition at the shop",
        "hi": "दुकान पर अच्छी हालत में नहीं है",
        "bho": "दोकान पर ठीक हालत में नइखे",
    },
    "REMOVAL_REASON_SHOP_CLOSING": {
        "en": "The shop is closing",
        "hi": "दुकान बंद हो रही है",
        "bho": "दोकान बंद होखे जात बा",
    },
    "REMOVAL_REASON_OTHER": {
        "en": "Other reason",
        "hi": "अन्य कारण",
        "bho": "दोसर कारण",
    },
    "ORDER_NOTICE_ITEMS_REMOVED": {
        "en": "{count} item(s) in your order are not available, so they were removed. The rest of your order will be delivered. Your new total is ₹{total}.",
        "hi": "आपके ऑर्डर की {count} चीज़ें उपलब्ध नहीं हैं, इसलिए हटा दी गई हैं। बाकी ऑर्डर पहुँचाया जाएगा। आपका नया कुल ₹{total} है।",
        "bho": "रउरा ऑर्डर के {count} सामान उपलब्ध नइखे, एहसे हटा दिहल गइल। बाकी ऑर्डर पहुँचावल जाई। रउरा नया कुल ₹{total} बा।",
    },
    "ORDER_NOTICE_ALL_REMOVED": {
        "en": "None of the items could be supplied, so your order was cancelled. You will not be charged.",
        "hi": "कोई भी सामान उपलब्ध नहीं हो सका, इसलिए आपका ऑर्डर रद्द कर दिया गया। आपसे कोई पैसा नहीं लिया जाएगा।",
        "bho": "कउनो सामान उपलब्ध ना हो सकल, एहसे रउरा ऑर्डर रद्द हो गइल। रउरा से पइसा ना लिहल जाई।",
    },
        "ORDER_NOTICE_ITEMS_REMOVED_FEE": {
        "en": "{count} item(s) in your order are not available, so they were removed. Your order is now below ₹{free_from}, so a delivery charge of ₹{fee} was added. Your new total is ₹{total}.",
        "hi": "आपके ऑर्डर की {count} चीज़ें उपलब्ध नहीं हैं, इसलिए हटा दी गई हैं। अब आपका ऑर्डर ₹{free_from} से कम है, इसलिए ₹{fee} डिलीवरी चार्ज लगा है। आपका नया कुल ₹{total} है।",
        "bho": "रउरा ऑर्डर के {count} सामान उपलब्ध नइखे, एहसे हटा दिहल गइल। अब रउरा ऑर्डर ₹{free_from} से कम बा, एहसे ₹{fee} डिलीवरी चार्ज लागल बा। रउरा नया कुल ₹{total} बा।",
    },
    "ORDER_NOTICE_CAN_CANCEL": {
        "en": "If you do not want the rest of the order, you can cancel it now.",
        "hi": "अगर आप बाकी ऑर्डर नहीं चाहते, तो अभी रद्द कर सकते हैं।",
        "bho": "अगर रउरा बाकी ऑर्डर ना चाहीं, त अभी रद्द कर सकीला।",
    },
    "ACCEPT_WAIT": {
        "en": "You removed items. Please wait 2 minutes so the customer can decide, then accept.",
        "hi": "आपने आइटम हटाए हैं। ग्राहक को फ़ैसला करने का समय देने के लिए 2 मिनट बाद स्वीकार करें।",
        "bho": "रउआ सामान हटवनी। ग्राहक के फैसला के समय देवे खातिर 2 मिनट बाद स्वीकार करीं।",
    },
        "PARTNER_EXISTS": {
        "en": "Your delivery partner application already exists.",
        "hi": "आपका डिलीवरी पार्टनर आवेदन पहले से मौजूद है।",
        "bho": "रउरा डिलीवरी पार्टनर आवेदन पहिलहीं से बा।",
    },
    "NOT_A_PARTNER": {
        "en": "Please apply as a delivery partner first.",
        "hi": "पहले डिलीवरी पार्टनर के लिए आवेदन करें।",
        "bho": "पहिले डिलीवरी पार्टनर खातिर आवेदन करीं।",
    },
    "PARTNER_NOT_FOUND": {
        "en": "Delivery partner not found.",
        "hi": "डिलीवरी पार्टनर नहीं मिला।",
        "bho": "डिलीवरी पार्टनर ना मिलल।",
    },
    "PARTNER_NOT_ACTIVE": {
        "en": "Your delivery partner account is not active yet.",
        "hi": "आपका डिलीवरी पार्टनर अकाउंट अभी सक्रिय नहीं है।",
        "bho": "रउरा डिलीवरी पार्टनर अकाउंट अभी चालू नइखे।",
    },
    "PARTNER_PHOTO_NOT_FOUND": {
        "en": "This photo is not available.",
        "hi": "यह फ़ोटो उपलब्ध नहीं है।",
        "bho": "ई फोटो उपलब्ध नइखे।",
    },
    "VEHICLE_NUMBER_REQUIRED": {
        "en": "Vehicle number is required for a bike or scooter.",
        "hi": "बाइक या स्कूटर का नंबर लिखना ज़रूरी है।",
        "bho": "बाइक चाहे स्कूटर के नंबर लिखल जरूरी बा।",
    },
    "VEHICLE_NUMBER_INVALID": {
        "en": "The vehicle number is not valid.",
        "hi": "गाड़ी का नंबर सही नहीं है।",
        "bho": "गाड़ी के नंबर सही नइखे।",
    },
        "ORDER_NOT_AVAILABLE": {
        "en": "This order is no longer available.",
        "hi": "यह ऑर्डर अब उपलब्ध नहीं है।",
        "bho": "ई ऑर्डर अब उपलब्ध नइखे।",
    },
    "PARTNER_BUSY": {
        "en": "Please finish your current order first.",
        "hi": "पहले अपना चल रहा ऑर्डर पूरा करें।",
        "bho": "पहिले आपन चलत ऑर्डर पूरा करीं।",
    },
    "PARTNER_OFFLINE": {
        "en": "Please go online first.",
        "hi": "पहले ऑनलाइन हो जाइए।",
        "bho": "पहिले ऑनलाइन हो जाईं।",
    },
    "DELIVERY_NOT_FOUND": {
        "en": "You do not have this delivery (or it is already picked up).",
        "hi": "यह डिलीवरी आपके पास नहीं है (या पिकअप हो चुका है)।",
        "bho": "ई डिलीवरी रउरा लगे नइखे (चाहे पिकअप हो चुकल बा)।",
    },
    "NO_ACTIVE_DELIVERY": {
        "en": "You have no active order right now.",
        "hi": "अभी आपके पास कोई ऑर्डर नहीं है।",
        "bho": "अभी रउरा लगे कौनो ऑर्डर नइखे।",
    },
        "ORDER_TOO_FAR": {
        "en": "This order is outside your area.",
        "hi": "यह ऑर्डर आपके इलाके से बाहर है।",
        "bho": "ई ऑर्डर रउरा इलाका से बाहर बा।",
    },
        "STORE_NOT_READY": {
        "en": "The shop is still preparing the items.",
        "hi": "दुकान अभी सामान तैयार कर रही है।",
        "bho": "दुकान अभी सामान तइयार करत बा।",
    },
    "STORE_PART_NOT_FOUND": {
        "en": "This shop is not part of the order.",
        "hi": "इस ऑर्डर में यह दुकान नहीं है।",
        "bho": "ए ऑर्डर में ई दुकान नइखे।",
    },
    "ALREADY_PICKED_UP": {
        "en": "The items are already picked up, you can no longer give up this order.",
        "hi": "सामान उठ चुका है, अब ऑर्डर छोड़ नहीं सकते।",
        "bho": "सामान उठ चुकल बा, अब ऑर्डर छोड़ ना सकीं।",
    },
    "NOT_ALL_PICKED_UP": {
        "en": "Please pick up the items from all shops first.",
        "hi": "पहले सभी दुकानों से सामान उठाइए।",
        "bho": "पहिले सब दुकान से सामान उठाईं।",
    },
    "PARTNER_HAS_GOODS": {
        "en": "The partner is carrying the customer's items. Let the delivery finish first.",
        "hi": "पार्टनर के पास ग्राहक का सामान है, पहले डिलीवरी पूरी होने दें।",
        "bho": "पार्टनर लगे ग्राहक के सामान बा, पहिले डिलीवरी पूरा होखे दीं।",
    },
    "PARTNER_ON_DELIVERY": {
        "en": "Finish your current order before going offline.",
        "hi": "ऑफ़लाइन होने से पहले चल रहा ऑर्डर पूरा करें।",
        "bho": "ऑफलाइन होखे से पहिले चलत ऑर्डर पूरा करीं।",
    },
        "OTP_INVALID": {
        "en": "The OTP is wrong.",
        "hi": "OTP गलत है।",
        "bho": "OTP गलत बा।",
    },
    "OTP_LOCKED": {
        "en": "Too many wrong OTPs. Please try again after some time.",
        "hi": "बहुत ज़्यादा गलत OTP डाले गए। थोड़ी देर बाद फिर कोशिश करें।",
        "bho": "बहुत जादे गलत OTP डालल गइल। तनी देर बाद फेर कोशिश करीं।",
    },
        "DEPOSIT_EXCEEDS_CASH": {
        "en": "The partner does not have that much cash.",
        "hi": "पार्टनर के पास इतना कैश नहीं है।",
        "bho": "पार्टनर लगे एतना कैश नइखे।",
    },
    "DEPOSIT_CORRECTION_TOO_BIG": {
        "en": "A correction cannot be more than the cash deposited so far.",
        "hi": "सुधार अब तक जमा किए गए कैश से ज़्यादा नहीं हो सकता।",
        "bho": "सुधार अबले जमा कइल कैश से जादे ना हो सकेला।",
    },
        "NOTHING_PICKED_UP": {
        "en": "Nothing has been picked up yet, so give up the order instead.",
        "hi": "अभी सामान नहीं उठाया है, ऑर्डर छोड़ दें।",
        "bho": "अभी सामान नइखे उठल, ऑर्डर छोड़ दीं।",
    },
    "GOODS_IN_HAND": {
        "en": "The partner has the items. Mark the delivery as failed instead.",
        "hi": "पार्टनर के पास सामान है, डिलीवरी को फेल मार्क करें।",
        "bho": "पार्टनर लगे सामान बा, डिलीवरी के फेल मार्क करीं।",
    },
        "RETURN_NOT_FOUND": {
        "en": "No returned items found for this order.",
        "hi": "इस ऑर्डर का वापस आने वाला सामान नहीं मिला।",
        "bho": "एह ऑर्डर के वापस आवे वाला सामान ना मिलल।",
    },
        "CASH_LIMIT_REACHED": {
        "en": "You are holding the maximum cash allowed. Deposit your cash to get new orders.",
        "hi": "आपके पास कैश की सीमा तक पैसे हो गए हैं। नए ऑर्डर पाने के लिए पहले कैश जमा करें।",
        "bho": "रउरा लगे कैश के सीमा तक पइसा हो गइल बा। नया ऑर्डर पावे खातिर पहिले कैश जमा करीं।",
    },
        "PAYOUT_EXCEEDS_DUE": {
        "en": "The partner is not owed that much.",
        "hi": "पार्टनर का इतना पैसा बाकी नहीं है।",
        "bho": "पार्टनर के एतना पइसा बाकी नइखे।",
    },
    "PAYOUT_CORRECTION_TOO_BIG": {
        "en": "A correction cannot be more than the amount paid so far.",
        "hi": "सुधार अब तक दिए गए पैसे से ज़्यादा नहीं हो सकता।",
        "bho": "सुधार अबले दिहल पइसा से जादे ना हो सकेला।",
    },
        "NOTIFICATION_NOT_FOUND": {
        "en": "Notification not found.",
        "hi": "नोटिफिकेशन नहीं मिली।",
        "bho": "नोटिफिकेशन ना मिलल।",
    },
    "NOTIF_ORDER_ACCEPTED_TITLE": {
        "en": "Order accepted",
        "hi": "ऑर्डर स्वीकार हुआ",
        "bho": "ऑर्डर मान लिहल गइल",
    },
    "NOTIF_ORDER_ACCEPTED_BODY": {
        "en": "{order_no}: the shop has accepted your order.",
        "hi": "{order_no}: दुकान ने आपका ऑर्डर मान लिया है।",
        "bho": "{order_no}: दोकान रउरा ऑर्डर मान लेले बा।",
    },
    "NOTIF_ORDER_PARTNER_ASSIGNED_TITLE": {
        "en": "Delivery partner assigned",
        "hi": "डिलीवरी पार्टनर मिल गया",
        "bho": "डिलीवरी पार्टनर मिल गइल",
    },
    "NOTIF_ORDER_PARTNER_ASSIGNED_BODY": {
        "en": "{order_no}: a delivery partner will pick up your order.",
        "hi": "{order_no}: एक डिलीवरी पार्टनर आपका ऑर्डर लेने जाएगा।",
        "bho": "{order_no}: एगो डिलीवरी पार्टनर रउरा ऑर्डर लेवे जाई।",
    },
    "NOTIF_ORDER_OUT_FOR_DELIVERY_TITLE": {
        "en": "Order on the way",
        "hi": "ऑर्डर रास्ते में है",
        "bho": "ऑर्डर रस्ता में बा",
    },
    "NOTIF_ORDER_OUT_FOR_DELIVERY_BODY": {
        "en": "{order_no} is on its way to you.",
        "hi": "{order_no} आपके पास आ रहा है।",
        "bho": "{order_no} रउरा लगे आ रहल बा।",
    },
    "NOTIF_ORDER_DELIVERED_TITLE": {
        "en": "Order delivered",
        "hi": "ऑर्डर पहुँच गया",
        "bho": "ऑर्डर पहुँच गइल",
    },
    "NOTIF_ORDER_DELIVERED_BODY": {
        "en": "{order_no} has been delivered. Thank you!",
        "hi": "{order_no} पहुँचा दिया गया है। धन्यवाद!",
        "bho": "{order_no} पहुँचा दिहल गइल। धन्यवाद!",
    },
    "NOTIF_ORDER_CANCELLED_TITLE": {
        "en": "Order cancelled",
        "hi": "ऑर्डर रद्द हुआ",
        "bho": "ऑर्डर रद्द हो गइल",
    },
    "NOTIF_ORDER_CANCELLED_BODY": {
        "en": "{order_no} has been cancelled.",
        "hi": "{order_no} रद्द कर दिया गया है।",
        "bho": "{order_no} रद्द हो गइल बा।",
    },
    "NOTIF_ORDER_FAILED_DELIVERY_TITLE": {
        "en": "Delivery failed",
        "hi": "डिलीवरी नहीं हो पाई",
        "bho": "डिलीवरी ना हो पाइल",
    },
    "NOTIF_ORDER_FAILED_DELIVERY_BODY": {
        "en": "We could not deliver {order_no}.",
        "hi": "हम {order_no} की डिलीवरी नहीं कर पाए।",
        "bho": "हम {order_no} के डिलीवरी ना क पाइनी।",
    },
    "NOTIF_ORDER_ITEMS_REMOVED_TITLE": {
        "en": "Items removed from your order",
        "hi": "आपके ऑर्डर से सामान हटा",
        "bho": "रउरा ऑर्डर से सामान हटल",
    },
    "NOTIF_ORDER_ITEMS_REMOVED_BODY": {
        "en": "{store_name} could not give {count} item(s) of {order_no}. Check your new total; you can cancel within {minutes} minutes.",
        "hi": "{store_name} {order_no} के {count} सामान नहीं दे पाई। नया टोटल देखें; आप {minutes} मिनट में ऑर्डर रद्द कर सकते हैं।",
        "bho": "{store_name} {order_no} के {count} सामान ना दे पाइल। नया टोटल देखीं; रउरा {minutes} मिनट में ऑर्डर रद्द क सकेनी।",
    },
    "NOTIF_SELLER_NEW_ORDER_TITLE": {
        "en": "New order",
        "hi": "नया ऑर्डर",
        "bho": "नया ऑर्डर",
    },
    "NOTIF_SELLER_NEW_ORDER_BODY": {
        "en": "{order_no} for {store_name}. Open the app to accept it.",
        "hi": "{store_name} के लिए {order_no}। स्वीकार करने के लिए ऐप खोलें।",
        "bho": "{store_name} खातिर {order_no}। मान लेवे खातिर ऐप खोलीं।",
    },
    "NOTIF_PAYOUT_RECEIVED_TITLE": {
        "en": "Payment received",
        "hi": "भुगतान मिला",
        "bho": "भुगतान मिलल",
    },
    "NOTIF_PAYOUT_RECEIVED_BODY": {
        "en": "Admin paid you ₹{amount} for your deliveries.",
        "hi": "आपकी डिलीवरी की कमाई के ₹{amount} आपको दिए गए।",
        "bho": "रउरा डिलीवरी के कमाई के ₹{amount} दिहल गइल।",
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
def translate_fmt(code: str, lang: str, **params) -> str:
    """Jin messages me {count}, {total} jaise khali jagah hain unke liye."""
    return translate(code, lang).format(**params)