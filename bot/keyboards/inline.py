from aiogram.utils.keyboard import InlineKeyboardBuilder

def lang_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🇺🇿 O'zbekcha", callback_data="lang_uz")
    kb.button(text="🇷🇺 Русский", callback_data="lang_ru")
    kb.adjust(1)
    return kb.as_markup()

def main_menu_kb(t):
    kb = InlineKeyboardBuilder()
    kb.button(text="📚 Darslar", callback_data="menu_lessons")
    kb.button(text="✅ Tasdiqlash", callback_data="menu_checkin")
    kb.button(text="🎫 Promokod", callback_data="menu_promo")
    kb.button(text=t("btn_profile"), callback_data="menu_profile")
    kb.button(text=t("btn_premium"), callback_data="menu_premium")
    kb.button(text=t("btn_myid"), callback_data="menu_myid")
    kb.adjust(2, 2, 1, 1)
    return kb.as_markup()

def back_menu_kb(t):
    kb = InlineKeyboardBuilder()
    kb.button(text="◀️ Orqaga", callback_data="back_menu")
    return kb.as_markup()

def payment_approval_kb(payment_id):
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Tasdiqlash", callback_data=f"pay_ok:{payment_id}")
    kb.button(text="❌ Rad etish", callback_data=f"pay_no:{payment_id}")
    kb.adjust(1)
    return kb.as_markup()

def admin_menu_kb(t):
    kb = InlineKeyboardBuilder()
    kb.button(text=t("btn_users"), callback_data="adm_users")
    kb.button(text=t("btn_stats"), callback_data="adm_stats")
    kb.button(text="🎟 Promokodlar", callback_data="adm_promo")
    kb.button(text=t("btn_categories_mgmt"), callback_data="adm_cats")
    kb.button(text=t("btn_lessons_mgmt"), callback_data="adm_lessons")
    kb.button(text=t("btn_premium_mgmt"), callback_data="adm_prem")
    kb.button(text="📢 Kanallar", callback_data="adm_channels")
    kb.adjust(2, 2, 2, 1)
    return kb.as_markup()

def admin_cats_list_kb(cats, t):
    kb = InlineKeyboardBuilder()
    for c in cats:
        kb.button(text=f"❌ {c.title_uz}", callback_data=f"del_cat:{c.id}")
    kb.button(text="➕ Yangi qo'shish", callback_data="add_cat")
    kb.adjust(1)
    return kb.as_markup()

def admin_lessons_list_kb(lessons, t):
    kb = InlineKeyboardBuilder()
    for l in lessons:
        kb.button(text=f"❌ {l.title_uz}", callback_data=f"del_lesson:{l.id}")
    kb.button(text="➕ Yangi qo'shish", callback_data="add_lesson")
    kb.adjust(1)
    return kb.as_markup()

def admin_prem_list_kb(packages, t):
    kb = InlineKeyboardBuilder()
    for p in packages:
        kb.button(text=f"❌ {p.name_uz} ({p.price_uzs} UZS)", callback_data=f"del_prem:{p.id}")
    kb.button(text="➕ Yangi qo'shish", callback_data="add_prem")
    kb.adjust(1)
    return kb.as_markup()