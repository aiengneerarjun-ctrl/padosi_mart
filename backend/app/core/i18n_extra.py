"""Naye features ke messages (error code + notification text) yahan jodte hain. core/i18n.py ke MESSAGES me apne-aap mil jate hain.
Har message ke teeno bhasha (en, hi, bho) zaroori hain; {placeholder} teeno me ek jaise hone chahiye."""

EXTRA: dict[str, dict[str, str]] = {
    # ---------- Reviews ----------
    "REVIEWER_ANONYMOUS": {"en": "Customer", "hi": "ग्राहक", "bho": "ग्राहक"},
    "REVIEW_ORDER_NOT_DELIVERED": {
        "en": "You can review only after the order is delivered.",
        "hi": "रिव्यू ऑर्डर पहुँचने के बाद ही दे सकते हैं।",
        "bho": "रिव्यू ऑर्डर पहुँचला के बाद ही दे सकीला।",
    },
    "REVIEW_WINDOW_OVER": {
        "en": "The time to review this order is over.",
        "hi": "इस ऑर्डर का रिव्यू देने का समय बीत गया है।",
        "bho": "एह ऑर्डर के रिव्यू देवे के समय बीत गइल बा।",
    },
    "REVIEW_ALREADY_EXISTS": {
        "en": "You have already reviewed this.",
        "hi": "आप इसका रिव्यू पहले ही दे चुके हैं।",
        "bho": "रउरा एकर रिव्यू पहिलहीं दे चुकल बानी।",
    },
    "REVIEW_TARGET_NOT_FOUND": {
        "en": "There is nothing to review here for this order.",
        "hi": "इस ऑर्डर में इसका रिव्यू देने के लिए कुछ नहीं है।",
        "bho": "एह ऑर्डर में एकर रिव्यू देवे खातिर कुछ नइखे।",
    },
    "REVIEW_NOT_FOUND": {
        "en": "Review not found.",
        "hi": "रिव्यू नहीं मिला।",
        "bho": "रिव्यू ना मिलल।",
    },

    # ---------- Support tickets ----------
    "TICKET_NOT_FOUND": {"en": "Ticket not found.", "hi": "टिकट नहीं मिला।", "bho": "टिकट ना मिलल।"},
    "TICKET_CLOSED": {
        "en": "This ticket is closed. Please open a new ticket.",
        "hi": "यह टिकट बंद हो चुका है। कृपया नया टिकट खोलें।",
        "bho": "ई टिकट बंद हो गइल बा। कृपा करके नया टिकट खोलीं।",
    },
    "TICKET_LIMIT": {
        "en": "You already have too many open tickets. Please wait for a reply or close one.",
        "hi": "आपके पहले से बहुत सारे टिकट खुले हैं। जवाब का इंतज़ार करें या कोई टिकट बंद करें।",
        "bho": "रउरा पहिले से बहुत टिकट खुलल बा। जवाब के इंतजार करीं भा कवनो टिकट बंद करीं।",
    },
    "TICKET_MESSAGE_LIMIT": {
        "en": "This ticket has too many messages. Please open a new ticket.",
        "hi": "इस टिकट में बहुत सारे संदेश हो गए हैं। कृपया नया टिकट खोलें।",
        "bho": "एह टिकट में बहुत संदेश हो गइल बा। कृपा करके नया टिकट खोलीं।",
    },
    "TICKET_ROLE_NOT_ALLOWED": {
        "en": "You cannot raise a ticket in this role.",
        "hi": "आप इस रूप में टिकट नहीं खोल सकते।",
        "bho": "रउरा एह रूप में टिकट ना खोल सकीला।",
    },
    "NOTIF_TICKET_REPLIED_TITLE": {
        "en": "Reply from Padosi Support",
        "hi": "पड़ोसी सपोर्ट का जवाब",
        "bho": "पड़ोसी सपोर्ट के जवाब",
    },
    "NOTIF_TICKET_REPLIED_BODY": {
        "en": "{ticket_no}: our team has replied to your ticket.",
        "hi": "{ticket_no}: हमारी टीम ने आपके टिकट का जवाब दिया है।",
        "bho": "{ticket_no}: हमनी के टीम रउरा टिकट के जवाब देले बा।",
    },
    "NOTIF_TICKET_CLOSED_TITLE": {
        "en": "Ticket closed",
        "hi": "टिकट बंद हुआ",
        "bho": "टिकट बंद भइल",
    },
    "NOTIF_TICKET_CLOSED_BODY": {
        "en": "{ticket_no}: your ticket has been closed. Open a new one if you still need help.",
        "hi": "{ticket_no}: आपका टिकट बंद कर दिया गया है। मदद चाहिए तो नया टिकट खोलें।",
        "bho": "{ticket_no}: रउरा टिकट बंद कर दिहल गइल बा। मदद चाहीं त नया टिकट खोलीं।",
    },
}
