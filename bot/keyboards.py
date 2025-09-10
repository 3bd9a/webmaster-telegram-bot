from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup

def get_main_keyboard():
    """لوحة المفاتيح الرئيسية المحسنة"""
    keyboard = [
        [KeyboardButton("🌐 تنزيل موقع جديد")],
        [KeyboardButton("📁 تنزيلاتي السابقة"), KeyboardButton("⚙️ الإعدادات")],
        [KeyboardButton("📊 إحصائياتي"), KeyboardButton("❓ المساعدة")]
    ]
    return ReplyKeyboardMarkup(
        keyboard, 
        resize_keyboard=True, 
        selective=True,
        one_time_keyboard=False
    )

def get_download_options_keyboard():
    """أزرار خيارات التنزيل المحسنة"""
    keyboard = [
        [InlineKeyboardButton("🚀 تنزيل كامل (موصى به)", callback_data="download_full")],
        [InlineKeyboardButton("⚡ الصفحة الرئيسية فقط", callback_data="download_page")],
        [InlineKeyboardButton("⚙️ خيارات متقدمة", callback_data="download_custom")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_settings_keyboard():
    """أزرار الإعدادات المحسنة"""
    keyboard = [
        [InlineKeyboardButton("🎯 جودة التنزيل", callback_data="setting_quality")],
        [InlineKeyboardButton("📏 الحد الأقصى للحجم", callback_data="setting_size")],
        [InlineKeyboardButton("📊 عدد الصفحات", callback_data="setting_pages")],
        [InlineKeyboardButton("🖼️ أنواع الملفات", callback_data="setting_files")],
        [InlineKeyboardButton("🌍 اللغة", callback_data="setting_language")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_confirmation_keyboard():
    """أزرار التأكيد"""
    keyboard = [
        [InlineKeyboardButton("✅ نعم", callback_data="confirm_yes")],
        [InlineKeyboardButton("❌ لا", callback_data="confirm_no")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_cancel_keyboard():
    """زر الإلغاء"""
    keyboard = [
        [InlineKeyboardButton("❌ إلغاء التنزيل", callback_data="cancel_download")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_keyboard():
    """لوحة إدارة المشرف المحسنة"""
    keyboard = [
        [InlineKeyboardButton("📊 إحصائيات مفصلة", callback_data="admin_detailed_stats")],
        [InlineKeyboardButton("📢 إرسال رسالة جماعية", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🚫 حظر مستخدم", callback_data="admin_ban_user"),
         InlineKeyboardButton("✅ إلغاء حظر", callback_data="admin_unban_user")],
        [InlineKeyboardButton("🧹 تنظيف فوري", callback_data="admin_cleanup"),
         InlineKeyboardButton("🔄 إعادة تشغيل", callback_data="admin_restart")],
        [InlineKeyboardButton("📁 عرض السجلات", callback_data="admin_logs")],
        [InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_user_management_keyboard():
    """أزرار إدارة المستخدمين"""
    keyboard = [
        [InlineKeyboardButton("👥 قائمة المستخدمين", callback_data="admin_users_list")],
        [InlineKeyboardButton("🚫 حظر مستخدم", callback_data="admin_ban_user")],
        [InlineKeyboardButton("✅ فك حظر", callback_data="admin_unban_user")],
        [InlineKeyboardButton("📊 إحصائيات مستخدم", callback_data="admin_user_stats")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_admin")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_download_history_keyboard(downloads):
    """أزرار تاريخ التنزيلات"""
    keyboard = []
    for download in downloads[:5]:  # آخر 5 تنزيلات
        keyboard.append([
            InlineKeyboardButton(
                f"📥 {download.domain} - {download.created_at.strftime('%Y-%m-%d')}",
                callback_data=f"history_{download.id}"
            )
        ])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)

def get_quality_keyboard():
    """أزرار جودة التنزيل"""
    keyboard = [
        [InlineKeyboardButton("⚡ سريع (منخفض الجودة)", callback_data="quality_low")],
        [InlineKeyboardButton("💎 متوازن (متوسط)", callback_data="quality_medium")],
        [InlineKeyboardButton("🎯 كامل (أعلى جودة)", callback_data="quality_high")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_file_type_keyboard():
    """أزرار أنواع الملفات"""
    keyboard = [
        [InlineKeyboardButton("📄 HTML فقط", callback_data="files_html")],
        [InlineKeyboardButton("🎨 مع CSS والصور", callback_data="files_css_images")],
        [InlineKeyboardButton("🚀 كل الملفات", callback_data="files_all")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_retry_keyboard():
    """أزرار إعادة المحاولة"""
    keyboard = [
        [InlineKeyboardButton("🔄 إعادة المحاولة", callback_data="retry_download")],
        [InlineKeyboardButton("⚙️ تغيير الإعدادات", callback_data="change_settings")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_language_keyboard():
    """أزرار اختيار اللغة"""
    keyboard = [
        [InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar")],
        [InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")],
        [InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_premium_keyboard():
    """أزرار الترقية"""
    keyboard = [
        [InlineKeyboardButton("⭐ ترقية الآن", callback_data="premium_upgrade")],
        [InlineKeyboardButton("📊 مقارنة الخطط", callback_data="premium_compare")],
        [InlineKeyboardButton("❓ أسئلة شائعة", callback_data="premium_faq")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_feedback_keyboard():
    """أزرار التقييم"""
    keyboard = [
        [InlineKeyboardButton("⭐ 5 نجوم", callback_data="feedback_5")],
        [InlineKeyboardButton("⭐ 4 نجوم", callback_data="feedback_4")],
        [InlineKeyboardButton("⭐ 3 نجوم", callback_data="feedback_3")],
        [InlineKeyboardButton("💬 تقييم نصي", callback_data="feedback_text")]
    ]
    return InlineKeyboardMarkup(keyboard)
