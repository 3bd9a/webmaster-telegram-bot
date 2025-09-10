"""
معالجات المستخدمين العاديين
User Handlers for Regular Bot Operations
"""

from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime

from .base_handler import BaseHandler
from utils.helpers import is_valid_url
from bot.keyboards import get_main_keyboard
from utils.logger import logger

class UserHandlers(BaseHandler):
    """معالجات المستخدمين العاديين"""
    
    def __init__(self, parent):
        super().__init__(parent)
    
    async def initialize(self):
        """تهيئة معالجات المستخدمين"""
        logger.info("✅ تم تهيئة معالجات المستخدمين")
    
    async def cleanup(self):
        """تنظيف موارد معالجات المستخدمين"""
        logger.info("✅ تم تنظيف معالجات المستخدمين")
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالج أمر /start - رسالة الترحيب العربية"""
        try:
            user = update.effective_user
            
            # حفظ/تحديث بيانات المستخدم
            await self.save_user_to_db(user)
            
            welcome_text = f"""🌍 **أهلاً وسهلاً {user.first_name}!**

🤖 أنا **WebMaster Bot** - أفضل بوت لتنزيل المواقع في تيليجرام! 🚀

📊 **ما أقدمه لك:**
✅ تنزيل مواقع كاملة مع كافة الملفات
✅ دعم المواقع التفاعلية (JavaScript)
✅ حفظ HTML, CSS, JS, والصور
✅ ضغط تلقائي في ZIP جاهز للتحميل
✅ حفظ تاريخ تنزيلاتك
✅ إحصائيات مفصلة

🛠️ **طريقة الاستخدام:**
1️⃣ أرسل رابط الموقع الذي تريد تنزيله
2️⃣ انتظر بينما أقوم بالعمل
3️⃣ احصل على ملف ZIP يحتوي على الموقع بالكامل

🔥 **مميزات خاصة:**
⚡ تنزيل فائق السرعة
🧠 دعم ذكي للجافاسكريبت
🎨 حفظ التصميم الأصلي 100%
📱 يعمل بدون إنترنت بعد التنزيل

👨‍💻 **جرب الآن!** أرسل رابط أي موقع وشاهد السحر! ✨"""
            
            await update.message.reply_text(
                welcome_text, 
                parse_mode='Markdown', 
                reply_markup=get_main_keyboard()
            )
            
        except Exception as e:
            logger.error(f"❌ خطأ في معالج /start: {e}")
            await update.message.reply_text(
                "❌ حدث خطأ في بدء البوت. يرجى المحاولة مرة أخرى."
            )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة الرسائل النصية"""
        text = update.message.text.strip()
        user_id = update.effective_user.id
        
        # فحص الحظر
        if self.is_user_banned(user_id):
            await update.message.reply_text(
                "🚫 **تم حظرك من استخدام البوت**\n\n"
                "📞 للاستفسار عن سبب الحظر أو طلب إلغاء الحظر، تواصل مع المشرف."
            )
            return
        
        # كشف النشاط المشبوه
        if self.detect_suspicious_activity(user_id, 'message'):
            banned = self.add_warning(user_id, "نشاط مشبوه - رسائل متكررة")
            if banned:
                await update.message.reply_text(
                    "🚫 تم حظرك تلقائياً بسبب النشاط المشبوه.\n"
                    "📞 تواصل مع المشرف للاستفسار."
                )
                return
            else:
                await update.message.reply_text(
                    "⚠️ تحذير: تم رصد نشاط مشبوه. يرجى تقليل معدل الرسائل."
                )
        
        # معالجة الأزرار
        if text == "🌐 تنزيل موقع جديد":
            await update.message.reply_text(
                "📝 **أرسل رابط الموقع الذي تريد تنزيله:**\n\n"
                "🔒 **ملاحظات أمنية:**\n"
                "• يجب أن يبدأ الرابط بـ http:// أو https://\n"
                "• لا نقبل الروابط المحلية أو الداخلية\n"
                "• يتم فحص جميع الروابط تلقائياً\n\n"
                "💡 **مثال:** https://example.com"
            )
        elif text == "📁 تنزيلاتي السابقة":
            await self.history(update, context)
        elif text == "⚙️ الإعدادات":
            await self.settings(update, context)
        elif text == "📊 إحصائياتي":
            await self.stats(update, context)
        elif text == "❓ المساعدة":
            await self.help_command(update, context)
        elif is_valid_url(text):
            # تفويض معالجة الروابط لمعالج التنزيل
            await self.parent.download_handlers.handle_url(update, context, text)
        else:
            await update.message.reply_text(
                "❓ **لم أفهم طلبك**\n\n"
                "🔹 استخدم الأزرار أدناه للتنقل\n"
                "🔹 أو أرسل رابط موقع للتنزيل\n"
                "🔹 اكتب /help للمساعدة",
                reply_markup=get_main_keyboard()
            )
    
    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض إحصائيات المستخدم"""
        try:
            user_id = update.effective_user.id
            
            # جلب الإحصائيات من قاعدة البيانات
            from database import get_db, Download
            from sqlalchemy import func
            
            db = next(get_db())
            
            # إحصائيات التنزيلات
            total_downloads = db.query(Download).filter(Download.user_id == user_id).count()
            successful_downloads = db.query(Download).filter(
                Download.user_id == user_id, 
                Download.status == 'completed'
            ).count()
            
            # حجم البيانات المحملة
            total_size = db.query(func.sum(Download.file_size)).filter(
                Download.user_id == user_id,
                Download.status == 'completed'
            ).scalar() or 0
            
            # آخر تنزيل
            last_download = db.query(Download).filter(
                Download.user_id == user_id
            ).order_by(Download.created_at.desc()).first()
            
            db.close()
            
            # تنسيق الحجم
            from utils.helpers import human_readable_size
            formatted_size = human_readable_size(total_size)
            
            # معدل النجاح
            success_rate = (successful_downloads / total_downloads * 100) if total_downloads > 0 else 0
            
            stats_text = f"""📊 **إحصائياتك الشخصية**

🔢 **إجمالي التنزيلات:** {total_downloads}
✅ **التنزيلات الناجحة:** {successful_downloads}
📈 **معدل النجاح:** {success_rate:.1f}%
💾 **إجمالي البيانات:** {formatted_size}

📅 **آخر تنزيل:** {last_download.created_at.strftime('%Y-%m-%d %H:%M') if last_download else 'لا يوجد'}

🏆 **مستوى النشاط:** {'🥇 نشط جداً' if total_downloads > 50 else '🥈 نشط' if total_downloads > 10 else '🥉 مبتدئ'}

💡 **نصيحة:** استخدم البوت بانتظام للحصول على أفضل النتائج!"""
            
            await update.message.reply_text(stats_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"❌ خطأ في عرض الإحصائيات: {e}")
            await update.message.reply_text(
                "❌ حدث خطأ في جلب الإحصائيات. يرجى المحاولة لاحقاً."
            )
    
    async def history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض تاريخ التنزيلات"""
        try:
            user_id = update.effective_user.id
            
            from database import get_db, Download
            db = next(get_db())
            
            # جلب آخر 10 تنزيلات
            downloads = db.query(Download).filter(
                Download.user_id == user_id
            ).order_by(Download.created_at.desc()).limit(10).all()
            
            db.close()
            
            if not downloads:
                await update.message.reply_text(
                    "📭 **لا توجد تنزيلات سابقة**\n\n"
                    "🌐 ابدأ بتنزيل أول موقع لك الآن!",
                    reply_markup=get_main_keyboard()
                )
                return
            
            history_text = "📁 **تاريخ تنزيلاتك**\n\n"
            
            for i, download in enumerate(downloads, 1):
                status_emoji = {
                    'completed': '✅',
                    'failed': '❌',
                    'in_progress': '⏳',
                    'cancelled': '🚫'
                }.get(download.status, '❓')
                
                from utils.helpers import human_readable_size
                size_text = human_readable_size(download.file_size) if download.file_size else 'غير محدد'
                
                history_text += f"{i}. {status_emoji} **{download.domain}**\n"
                history_text += f"   📅 {download.created_at.strftime('%Y-%m-%d %H:%M')}\n"
                history_text += f"   💾 {size_text}\n\n"
            
            history_text += "💡 **نصيحة:** يمكنك إعادة تنزيل أي موقع بإرسال رابطه مرة أخرى"
            
            await update.message.reply_text(history_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"❌ خطأ في عرض التاريخ: {e}")
            await update.message.reply_text(
                "❌ حدث خطأ في جلب التاريخ. يرجى المحاولة لاحقاً."
            )
    
    async def settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض إعدادات المستخدم"""
        from bot.keyboards import get_settings_keyboard
        
        settings_text = """⚙️ **إعدادات البوت**

🎯 **الإعدادات الحالية:**
• جودة التنزيل: عالية
• الحد الأقصى للحجم: 50 MB
• عدد الصفحات: غير محدود
• أنواع الملفات: جميع الأنواع
• اللغة: العربية

🔧 **اختر الإعداد الذي تريد تعديله:**"""
        
        await update.message.reply_text(
            settings_text,
            parse_mode='Markdown',
            reply_markup=get_settings_keyboard()
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض المساعدة"""
        help_text = """❓ **مساعدة البوت**

🤖 **أوامر البوت:**
/start - بدء البوت
/help - عرض المساعدة
/stats - إحصائياتك
/history - تاريخ التنزيلات
/settings - الإعدادات
/cancel - إلغاء التنزيل الحالي

🌐 **كيفية التنزيل:**
1. أرسل رابط الموقع
2. انتظر معالجة الطلب
3. احصل على ملف ZIP

🔒 **الأمان:**
• يتم فحص جميع الروابط
• لا نحفظ محتوى المواقع
• بياناتك آمنة ومحمية

📞 **الدعم:**
إذا واجهت أي مشكلة، تواصل مع المشرف

💡 **نصائح:**
• استخدم روابط مباشرة للمواقع
• تجنب الروابط المشبوهة
• انتظر انتهاء التنزيل قبل طلب آخر"""
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
