"""
معالجات الأزرار والاستعلامات
Callback and Button Handlers
"""

from telegram import Update
from telegram.ext import ContextTypes

from .base_handler import BaseHandler
from bot.keyboards import (
    get_main_keyboard, get_settings_keyboard, get_admin_keyboard,
    get_confirmation_keyboard, get_quality_keyboard, get_file_type_keyboard
)
from utils.logger import logger

class CallbackHandlers(BaseHandler):
    """معالجات الأزرار والاستعلامات"""
    
    def __init__(self, parent):
        super().__init__(parent)
    
    async def initialize(self):
        """تهيئة معالجات الأزرار"""
        logger.info("✅ تم تهيئة معالجات الأزرار")
    
    async def cleanup(self):
        """تنظيف موارد معالجات الأزرار"""
        logger.info("✅ تم تنظيف معالجات الأزرار")
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالج الأزرار الرئيسي"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id
        
        try:
            # أزرار التنقل الأساسية
            if data == "back_main":
                await self._handle_back_main(query, context)
            elif data == "back_admin":
                await self._handle_back_admin(query, context)
            
            # أزرار التنزيل
            elif data.startswith("download_"):
                await self._handle_download_options(query, context, data)
            
            # أزرار الإعدادات
            elif data.startswith("setting_"):
                await self._handle_settings(query, context, data)
            
            # أزرار الإدارة
            elif data.startswith("admin_"):
                await self._handle_admin_actions(query, context, data)
            
            # أزرار التأكيد
            elif data.startswith("confirm_"):
                await self._handle_confirmation(query, context, data)
            
            # أزرار الجودة
            elif data.startswith("quality_"):
                await self._handle_quality_selection(query, context, data)
            
            # أزرار أنواع الملفات
            elif data.startswith("files_"):
                await self._handle_file_types(query, context, data)
            
            # أزرار التاريخ
            elif data.startswith("history_"):
                await self._handle_history_item(query, context, data)
            
            # إلغاء التنزيل
            elif data == "cancel_download":
                await self._handle_cancel_download(query, context)
            
            else:
                await query.edit_message_text(
                    "❓ خيار غير معروف. يرجى المحاولة مرة أخرى.",
                    reply_markup=get_main_keyboard()
                )
                
        except Exception as e:
            logger.error(f"❌ خطأ في معالج الأزرار: {e}")
            await query.edit_message_text(
                "❌ حدث خطأ في معالجة الطلب. يرجى المحاولة مرة أخرى."
            )
    
    async def _handle_back_main(self, query, context):
        """العودة للقائمة الرئيسية"""
        await query.edit_message_text(
            "🏠 **القائمة الرئيسية**\n\n"
            "اختر ما تريد فعله:",
            parse_mode='Markdown',
            reply_markup=get_main_keyboard()
        )
    
    async def _handle_back_admin(self, query, context):
        """العودة لقائمة الإدارة"""
        if not self.parent.admin_handlers._is_admin(query.from_user.id):
            await query.edit_message_text("🚫 غير مصرح لك بالوصول")
            return
        
        await query.edit_message_text(
            "🛡️ **لوحة تحكم المشرف**\n\n"
            "اختر العملية المطلوبة:",
            parse_mode='Markdown',
            reply_markup=get_admin_keyboard()
        )
    
    async def _handle_download_options(self, query, context, data):
        """معالجة خيارات التنزيل"""
        if data == "download_full":
            await query.edit_message_text(
                "🚀 **تنزيل كامل**\n\n"
                "سيتم تنزيل الموقع بالكامل مع جميع الملفات والموارد.\n\n"
                "📝 أرسل رابط الموقع الآن:",
                parse_mode='Markdown'
            )
        elif data == "download_page":
            await query.edit_message_text(
                "⚡ **الصفحة الرئيسية فقط**\n\n"
                "سيتم تنزيل الصفحة الرئيسية فقط مع الموارد الأساسية.\n\n"
                "📝 أرسل رابط الموقع الآن:",
                parse_mode='Markdown'
            )
        elif data == "download_custom":
            await query.edit_message_text(
                "⚙️ **خيارات متقدمة**\n\n"
                "اختر إعدادات التنزيل المخصصة:",
                parse_mode='Markdown',
                reply_markup=get_settings_keyboard()
            )
    
    async def _handle_settings(self, query, context, data):
        """معالجة إعدادات البوت"""
        if data == "setting_quality":
            await query.edit_message_text(
                "🎯 **جودة التنزيل**\n\n"
                "اختر مستوى الجودة المطلوب:",
                parse_mode='Markdown',
                reply_markup=get_quality_keyboard()
            )
        elif data == "setting_size":
            await query.edit_message_text(
                "📏 **الحد الأقصى للحجم**\n\n"
                "الحد الحالي: 50 MB\n\n"
                "💡 هذا الإعداد يحمي الخادم من التحميل الزائد",
                parse_mode='Markdown'
            )
        elif data == "setting_pages":
            await query.edit_message_text(
                "📊 **عدد الصفحات**\n\n"
                "العدد الحالي: غير محدود\n\n"
                "💡 يمكن تحديد عدد أقصى للصفحات لتوفير الوقت",
                parse_mode='Markdown'
            )
        elif data == "setting_files":
            await query.edit_message_text(
                "🖼️ **أنواع الملفات**\n\n"
                "اختر أنواع الملفات المطلوب تنزيلها:",
                parse_mode='Markdown',
                reply_markup=get_file_type_keyboard()
            )
        elif data == "setting_language":
            await query.edit_message_text(
                "🌍 **اللغة**\n\n"
                "اللغة الحالية: العربية 🇸🇦\n\n"
                "💡 المزيد من اللغات قريباً!",
                parse_mode='Markdown'
            )
    
    async def _handle_admin_actions(self, query, context, data):
        """معالجة أعمال الإدارة"""
        user_id = query.from_user.id
        
        if not self.parent.admin_handlers._is_admin(user_id):
            await query.edit_message_text("🚫 غير مصرح لك بالوصول")
            return
        
        if data == "admin_detailed_stats":
            await self._show_detailed_stats(query, context)
        elif data == "admin_broadcast":
            await query.edit_message_text(
                "📢 **إرسال رسالة جماعية**\n\n"
                "📝 استخدم الأمر: `/broadcast رسالتك هنا`\n\n"
                "⚠️ تأكد من صياغة الرسالة بعناية قبل الإرسال",
                parse_mode='Markdown'
            )
        elif data == "admin_ban_user":
            await query.edit_message_text(
                "🚫 **حظر مستخدم**\n\n"
                "📝 استخدم الأمر: `/ban معرف_المستخدم`\n\n"
                "💡 مثال: `/ban 123456789`",
                parse_mode='Markdown'
            )
        elif data == "admin_unban_user":
            await query.edit_message_text(
                "✅ **إلغاء حظر مستخدم**\n\n"
                "📝 استخدم الأمر: `/unban معرف_المستخدم`\n\n"
                "💡 مثال: `/unban 123456789`",
                parse_mode='Markdown'
            )
        elif data == "admin_cleanup":
            await self.parent.admin_handlers.cleanup_command(
                type('obj', (object,), {'message': query, 'effective_user': query.from_user})(),
                context
            )
        elif data == "admin_logs":
            await self._show_recent_logs(query, context)
    
    async def _handle_confirmation(self, query, context, data):
        """معالجة أزرار التأكيد"""
        if data == "confirm_yes":
            await query.edit_message_text(
                "✅ **تم التأكيد**\n\n"
                "سيتم تنفيذ العملية...",
                parse_mode='Markdown'
            )
        elif data == "confirm_no":
            await query.edit_message_text(
                "❌ **تم الإلغاء**\n\n"
                "لم يتم تنفيذ أي عملية.",
                parse_mode='Markdown',
                reply_markup=get_main_keyboard()
            )
    
    async def _handle_quality_selection(self, query, context, data):
        """معالجة اختيار الجودة"""
        quality_map = {
            "quality_low": "⚡ سريع (منخفض الجودة)",
            "quality_medium": "💎 متوازن (متوسط)",
            "quality_high": "🎯 كامل (أعلى جودة)"
        }
        
        selected_quality = quality_map.get(data, "غير محدد")
        
        await query.edit_message_text(
            f"✅ **تم تحديد الجودة**\n\n"
            f"🎯 الجودة المختارة: {selected_quality}\n\n"
            f"💡 سيتم استخدام هذا الإعداد في التنزيلات القادمة",
            parse_mode='Markdown',
            reply_markup=get_main_keyboard()
        )
    
    async def _handle_file_types(self, query, context, data):
        """معالجة اختيار أنواع الملفات"""
        file_type_map = {
            "files_html": "📄 HTML فقط",
            "files_css_images": "🎨 مع CSS والصور",
            "files_all": "🚀 كل الملفات"
        }
        
        selected_type = file_type_map.get(data, "غير محدد")
        
        await query.edit_message_text(
            f"✅ **تم تحديد أنواع الملفات**\n\n"
            f"🖼️ النوع المختار: {selected_type}\n\n"
            f"💡 سيتم تطبيق هذا الإعداد على التنزيلات القادمة",
            parse_mode='Markdown',
            reply_markup=get_main_keyboard()
        )
    
    async def _handle_history_item(self, query, context, data):
        """معالجة عنصر من التاريخ"""
        try:
            download_id = int(data.split('_')[1])
            
            from database import get_db, Download
            db = next(get_db())
            download = db.query(Download).filter(Download.id == download_id).first()
            db.close()
            
            if not download:
                await query.edit_message_text("❌ لم يتم العثور على التنزيل")
                return
            
            status_emoji = {
                'completed': '✅',
                'failed': '❌',
                'in_progress': '⏳',
                'cancelled': '🚫'
            }.get(download.status, '❓')
            
            from utils.helpers import human_readable_size
            size_text = human_readable_size(download.file_size) if download.file_size else 'غير محدد'
            
            history_detail = f"{status_emoji} **تفاصيل التنزيل**\n\n"
            history_detail += f"🌐 **الموقع:** {download.domain}\n"
            history_detail += f"🔗 **الرابط:** {download.url[:50]}...\n"
            history_detail += f"📅 **التاريخ:** {download.created_at.strftime('%Y-%m-%d %H:%M')}\n"
            history_detail += f"💾 **الحجم:** {size_text}\n"
            history_detail += f"📊 **الحالة:** {download.status}\n"
            
            if download.error_message:
                history_detail += f"⚠️ **الخطأ:** {download.error_message}\n"
            
            await query.edit_message_text(
                history_detail,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"❌ خطأ في عرض تفاصيل التنزيل: {e}")
            await query.edit_message_text("❌ حدث خطأ في عرض التفاصيل")
    
    async def _handle_cancel_download(self, query, context):
        """معالجة إلغاء التنزيل"""
        user_id = query.from_user.id
        
        if user_id not in self.active_downloads:
            await query.edit_message_text(
                "❌ **لا يوجد تنزيل نشط للإلغاء**\n\n"
                "💡 يمكنك بدء تنزيل جديد بإرسال رابط الموقع",
                parse_mode='Markdown'
            )
            return
        
        # تفويض الإلغاء لمعالج التنزيل
        await self.parent.download_handlers.cancel(
            type('obj', (object,), {'message': query, 'effective_user': query.from_user})(),
            context
        )
    
    async def _show_detailed_stats(self, query, context):
        """عرض إحصائيات مفصلة"""
        try:
            from database import get_db, Download, User
            from datetime import datetime, timedelta
            import psutil
            
            db = next(get_db())
            
            # إحصائيات عامة
            total_users = db.query(User).count()
            total_downloads = db.query(Download).count()
            successful_downloads = db.query(Download).filter(Download.status == 'completed').count()
            
            # إحصائيات الشهر الماضي
            month_ago = datetime.utcnow() - timedelta(days=30)
            month_downloads = db.query(Download).filter(Download.created_at >= month_ago).count()
            month_users = db.query(User).filter(User.created_at >= month_ago).count()
            
            # أكثر النطاقات تنزيلاً
            from sqlalchemy import func
            top_domains = db.query(
                Download.domain, 
                func.count(Download.id).label('count')
            ).group_by(Download.domain).order_by(func.count(Download.id).desc()).limit(5).all()
            
            db.close()
            
            # معلومات النظام
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent()
            
            stats_text = f"""📊 **إحصائيات مفصلة**

👥 **المستخدمون:**
• إجمالي المستخدمين: {total_users}
• مستخدمين جدد (30 يوم): {month_users}
• مستخدمين محظورين: {len(self.banned_users)}

📥 **التنزيلات:**
• إجمالي التنزيلات: {total_downloads}
• تنزيلات ناجحة: {successful_downloads}
• تنزيلات الشهر: {month_downloads}
• تنزيلات نشطة: {len(self.active_downloads)}

🏆 **أكثر المواقع تنزيلاً:**"""
            
            for i, (domain, count) in enumerate(top_domains, 1):
                stats_text += f"\n{i}. {domain}: {count} مرة"
            
            stats_text += f"""

🖥️ **النظام:**
• استخدام المعالج: {cpu_percent:.1f}%
• استخدام الذاكرة: {memory.percent:.1f}%
• تحذيرات نشطة: {len(self.user_warnings)}"""
            
            await query.edit_message_text(
                stats_text,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"❌ خطأ في الإحصائيات المفصلة: {e}")
            await query.edit_message_text("❌ حدث خطأ في جلب الإحصائيات")
    
    async def _show_recent_logs(self, query, context):
        """عرض السجلات الحديثة"""
        try:
            import os
            log_file = os.path.join(config.Config.LOGS_DIR, "webmaster_bot.log")
            
            if not os.path.exists(log_file):
                await query.edit_message_text("❌ لا توجد ملفات سجلات")
                return
            
            # قراءة آخر 20 سطر
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                recent_lines = lines[-20:] if len(lines) > 20 else lines
            
            logs_text = "📋 **السجلات الحديثة:**\n\n```\n"
            for line in recent_lines:
                if len(logs_text) + len(line) > 4000:  # حد تيليجرام
                    break
                logs_text += line
            logs_text += "```"
            
            await query.edit_message_text(
                logs_text,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"❌ خطأ في عرض السجلات: {e}")
            await query.edit_message_text("❌ حدث خطأ في عرض السجلات")
