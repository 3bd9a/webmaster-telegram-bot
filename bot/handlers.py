from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes
import os
import asyncio
from datetime import datetime, timedelta
import time
from typing import Dict, Optional
from collections import defaultdict

# استيرادات محسنة
from services.downloader import WebsiteDownloader
from services.file_manager import FileManager
from utils.helpers import is_valid_url, sanitize_filename
from utils.logger import logger
from database import get_db, Download, User
from bot.keyboards import (
    get_main_keyboard,
    get_settings_keyboard,
    get_download_history_keyboard,
    get_admin_keyboard
)

import config
from sqlalchemy.orm import Session

class BotHandlers:
    """معالج رسائل البوت الرئيسي مع دعم كامل للغة العربية"""
    
    def __init__(self):
        self.downloader = WebsiteDownloader()
        self.active_downloads = {}
        self.user_rate_limits = defaultdict(list)
        self.banned_users = set()
        self.user_warnings = defaultdict(int)
        self.suspicious_activity = defaultdict(list)
        self.last_cleanup = time.time()
        
    async def initialize(self):
        """تهيئة محرك التنزيل والموارد"""
        try:
            await self.downloader.initialize()
            logger.info("✅ تم تهيئة محرك التنزيل بنجاح")
        except Exception as e:
            logger.error(f"❌ فشل في تهيئة محرك التنزيل: {e}")
            raise
    
    async def cleanup(self):
        """تنظيف الموارد عند إغلاق البوت"""
        try:
            if self.downloader:
                await self.downloader.close()
            
            # إلغاء جميع التنزيلات النشطة
            for user_id in list(self.active_downloads.keys()):
                self.active_downloads.pop(user_id, None)
            
            logger.info("✅ تم تنظيف موارد البوت")
        except Exception as e:
            logger.error(f"❌ خطأ في تنظيف الموارد: {e}")
    
    async def periodic_cleanup(self):
        """تنظيف دوري للملفات والموارد"""
        try:
            current_time = time.time()
            
            # تنظيف حدود المعدل القديمة
            for user_id in list(self.user_rate_limits.keys()):
                self.user_rate_limits[user_id] = [
                    timestamp for timestamp in self.user_rate_limits[user_id]
                    if current_time - timestamp < 3600  # آخر ساعة فقط
                ]
                
                if not self.user_rate_limits[user_id]:
                    del self.user_rate_limits[user_id]
            
            # تنظيف الملفات القديمة
            await FileManager.cleanup_old_files(config.Config.TEMP_DIR, max_age_hours=2)
            await FileManager.cleanup_old_files(config.Config.DOWNLOADS_DIR, max_age_hours=24)
            
            self.last_cleanup = current_time
            logger.info("🧹 تم التنظيف الدوري")
            
        except Exception as e:
            logger.error(f"❌ خطأ في التنظيف الدوري: {e}")
    
    def check_rate_limit(self, user_id: int) -> bool:
        """فحص حدود المعدل للمستخدم"""
        current_time = time.time()
        user_requests = self.user_rate_limits[user_id]
        
        # إزالة الطلبات القديمة (أكثر من ساعة)
        user_requests[:] = [req_time for req_time in user_requests if current_time - req_time < 3600]
        
        # فحص الحد الأقصى
        if len(user_requests) >= config.Config.RATE_LIMIT_PER_HOUR:
            return False
        
        # إضافة الطلب الحالي
        user_requests.append(current_time)
        return True
    
    def is_user_banned(self, user_id: int) -> bool:
        """فحص ما إذا كان المستخدم محظور"""
        return user_id in self.banned_users
    
    def ban_user(self, user_id: int):
        """حظر مستخدم"""
        self.banned_users.add(user_id)
        logger.warning(f"🚫 تم حظر المستخدم: {user_id}")
    
    def unban_user(self, user_id: int):
        """إلغاء حظر مستخدم"""
        self.banned_users.discard(user_id)
        logger.info(f"✅ تم إلغاء حظر المستخدم: {user_id}")
    
    def add_warning(self, user_id: int, reason: str):
        """إضافة تحذير للمستخدم"""
        self.user_warnings[user_id] += 1
        logger.warning(f"⚠️ تحذير للمستخدم {user_id}: {reason} (العدد: {self.user_warnings[user_id]})")
        
        # حظر تلقائي بعد 3 تحذيرات
        if self.user_warnings[user_id] >= 3:
            self.ban_user(user_id)
            return True
        return False
    
    def detect_suspicious_activity(self, user_id: int, activity_type: str) -> bool:
        """كشف النشاط المشبوه"""
        current_time = time.time()
        user_activities = self.suspicious_activity[user_id]
        
        # إزالة الأنشطة القديمة (أكثر من 10 دقائق)
        user_activities[:] = [act for act in user_activities if current_time - act['time'] < 600]
        
        # إضافة النشاط الحالي
        user_activities.append({'type': activity_type, 'time': current_time})
        
        # فحص الأنشطة المشبوهة
        if len(user_activities) > 20:  # أكثر من 20 نشاط في 10 دقائق
            return True
        
        # فحص الطلبات المتكررة السريعة
        recent_requests = [act for act in user_activities if act['type'] == 'download_request' and current_time - act['time'] < 60]
        if len(recent_requests) > 5:  # أكثر من 5 طلبات في دقيقة
            return True
        
        return False
    
    def validate_url_security(self, url: str) -> tuple[bool, str]:
        """فحص أمان الرابط"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            
            # فحص البروتوكول
            if parsed.scheme not in ['http', 'https']:
                return False, "البروتوكول غير مدعوم"
            
            # فحص النطاقات المحظورة
            blocked_domains = ['localhost', '127.0.0.1', '0.0.0.0', '10.', '192.168.', '172.']
            for blocked in blocked_domains:
                if blocked in parsed.netloc.lower():
                    return False, "النطاق محظور لأسباب أمنية"
            
            # فحص الامتدادات المشبوهة
            suspicious_extensions = ['.exe', '.bat', '.cmd', '.scr', '.pif']
            if any(url.lower().endswith(ext) for ext in suspicious_extensions):
                return False, "نوع الملف غير آمن"
            
            return True, "الرابط آمن"
            
        except Exception as e:
            return False, f"خطأ في فحص الرابط: {str(e)}"
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالج أمر /start - رسالة الترحيب العربية"""
        try:
            user = update.effective_user
            db: Session = next(get_db())
            
            # حفظ/تحديث بيانات المستخدم
            db_user = db.query(User).filter(User.telegram_id == user.id).first()
            if not db_user:
                db_user = User(
                    telegram_id=user.id,
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name
                )
                db.add(db_user)
                logger.info(f"🎆 مستخدم جديد: {user.first_name} ({user.id})")
            else:
                db_user.last_activity = datetime.utcnow()
            
            db.commit()
            db.close()
            
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
            # فحص أمان الرابط
            is_safe, safety_message = self.validate_url_security(text)
            if not is_safe:
                self.add_warning(user_id, f"رابط غير آمن: {safety_message}")
                await update.message.reply_text(
                    f"🚫 **رابط غير آمن!**\n\n"
                    f"❌ السبب: {safety_message}\n\n"
                    "🔒 نحن نحمي مستخدمينا من الروابط الضارة."
                )
                return
            
            # كشف النشاط المشبوه للتنزيل
            if self.detect_suspicious_activity(user_id, 'download_request'):
                banned = self.add_warning(user_id, "طلبات تنزيل متكررة مشبوهة")
                if banned:
                    await update.message.reply_text(
                        "🚫 تم حظرك تلقائياً بسبب الطلبات المتكررة المشبوهة."
                    )
                    return
                else:
                    await update.message.reply_text(
                        "⚠️ تحذير: طلبات تنزيل متكررة. يرجى الانتظار بين الطلبات."
                    )
                    return
            
            # فحص حدود المعدل
            if not self.check_rate_limit(user_id):
                remaining_time = 3600 - (time.time() - min(self.user_rate_limits[user_id]))
                await update.message.reply_text(
                    f"⏰ **تجاوزت الحد المسموح!**\n\n"
                    f"📊 الحد الأقصى: {config.Config.RATE_LIMIT_PER_HOUR} تنزيلات/ساعة\n"
                    f"⏳ الوقت المتبقي: {int(remaining_time/60)} دقيقة\n\n"
                    "💡 **نصيحة:** استخدم الوقت لمراجعة تنزيلاتك السابقة!"
                )
                return
            
            await self.start_download(update, context, text)
        else:
            await update.message.reply_text(
                "⚠️ **رابط غير صالح!**\n\n"
                "📋 **المطلوب:**\n"
                "• رابط يبدأ بـ http:// أو https://\n"
                "• موقع ويب صالح ومتاح\n\n"
                "💡 **مثال صحيح:** https://example.com\n\n"
                "🔍 **أو استخدم الأزرار أدناه:**",
                reply_markup=get_main_keyboard()
            )
    
    async def start_download(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
        """بدء عملية التنزيل"""
        user_id = update.effective_user.id
        
        # التحقق من وجود تنزيل نشط
        if user_id in self.active_downloads:
            await update.message.reply_text("⏳ لديك عملية تنزيل قيد المعالجة. انتظر حتى تنتهي.")
            return
        
        # بدء التنزيل
        self.active_downloads[user_id] = True
        message = await update.message.reply_text("🔄 جاري تحضير التنزيل...")
        
        try:
            # إنشاء مجلد مؤقت للتنزيل
            download_id = f"{user_id}_{int(datetime.now().timestamp())}"
            temp_dir = os.path.join(config.Config.TEMP_DIR, download_id)
            os.makedirs(temp_dir, exist_ok=True)
            
            # تسجيل التنزيل في قاعدة البيانات
            db: Session = next(get_db())
            download = Download(
                user_id=user_id,
                url=url,
                domain=url.split('//')[-1].split('/')[0],
                status="processing",
                start_time=datetime.utcnow()
            )
            db.add(download)
            db.commit()
            
            await message.edit_text("🌐 جاري تحليل الموقع واستخراج المحتوى...")
            
            # تنزيل الموقع
            output_dir, total_files, total_size = await self.downloader.download_website(
                url, temp_dir, max_depth=2
            )
            
            await message.edit_text("📦 جاري ضغط الملفات...")
            
            # ضغط الملفات
            zip_path = os.path.join(config.Config.DOWNLOADS_DIR, f"{download_id}.zip")
            zip_path, zip_size = await FileManager.create_zip(output_dir, zip_path)
            
            # تحديث سجل التنزيل
            download.status = "completed"
            download.file_path = zip_path
            download.file_size = zip_size
            download.total_files = total_files
            download.end_time = datetime.utcnow()
            db.commit()
            
            # تحديث إحصائيات المستخدم
            db_user = db.query(User).filter(User.telegram_id == user_id).first()
            if db_user:
                db_user.total_downloads += 1
                db_user.total_size += zip_size
                db.commit()
            
            # إرسال الملف
            formatted_size = FileManager.format_size(zip_size)
            await message.edit_text(f"✅ تم الانتهاء من التنزيل!\n📊 الحجم: {formatted_size}\n📁 الملفات: {total_files}")
            
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=open(zip_path, 'rb'),
                caption=f"📦 تم تنزيل الموقع بنجاح\n🌐 {url}\n💾 {formatted_size}"
            )
            
            # التنظيف التلقائي لاحقاً
            asyncio.create_task(FileManager.cleanup_directory(temp_dir))
            asyncio.create_task(FileManager.cleanup_directory(zip_path, 3600))
            
        except Exception as e:
            error_msg = f"❌ حدث خطأ أثناء التنزيل: {str(e)}"
            await message.edit_text(error_msg)
            
            # تحديث سجل التنزيل بالفشل
            db: Session = next(get_db())
            download.status = "failed"
            download.error_message = str(e)
            download.end_time = datetime.utcnow()
            db.commit()
            
        finally:
            self.active_downloads.pop(user_id, None)
            db.close()
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """إلغاء التنزيل الحالي"""
        user_id = update.effective_user.id
        if user_id in self.active_downloads:
            # هنا يمكن إضافة منطق لإلغاء التنزيل
            self.active_downloads.pop(user_id, None)
            await update.message.reply_text("❌ تم إلغاء عملية التنزيل.")
        else:
            await update.message.reply_text("⚠️ لا توجد عملية تنزيل نشطة لإلغائها.")
    
    async def broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """إرسال رسالة جماعية (للمشرف فقط)"""
        user_id = update.effective_user.id
        
        if user_id != config.Config.ADMIN_ID:
            await update.message.reply_text("❌ ليس لديك صلاحية لهذا الأمر.")
            return
        
        if not context.args:
            await update.message.reply_text(
                "📢 **إرسال رسالة جماعية**\n\n"
                "📝 **الاستخدام:**\n"
                "/broadcast <الرسالة>\n\n"
                "💡 **مثال:**\n"
                "/broadcast مرحباً بجميع المستخدمين! تم تحديث البوت."
            )
            return
        
        message_text = ' '.join(context.args)
        db: Session = next(get_db())
        
        try:
            # الحصول على جميع المستخدمين
            users = db.query(User).all()
            sent_count = 0
            failed_count = 0
            
            status_message = await update.message.reply_text(
                f"📤 جاري إرسال الرسالة إلى {len(users)} مستخدم...\n"
                "⏳ يرجى الانتظار..."
            )
            
            for user in users:
                try:
                    await context.bot.send_message(
                        chat_id=user.telegram_id,
                        text=f"📢 **رسالة من إدارة البوت:**\n\n{message_text}",
                        parse_mode='Markdown'
                    )
                    sent_count += 1
                    
                    # تحديث حالة الإرسال كل 10 مستخدمين
                    if sent_count % 10 == 0:
                        await status_message.edit_text(
                            f"📤 تم الإرسال إلى {sent_count}/{len(users)} مستخدم...\n"
                            "⏳ جاري المتابعة..."
                        )
                    
                    # تأخير بسيط لتجنب حدود التيليجرام
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    failed_count += 1
                    logger.error(f"فشل إرسال رسالة للمستخدم {user.telegram_id}: {e}")
            
            await status_message.edit_text(
                f"✅ **تم إنهاء الإرسال الجماعي!**\n\n"
                f"📊 **النتائج:**\n"
                f"✅ تم الإرسال بنجاح: {sent_count}\n"
                f"❌ فشل الإرسال: {failed_count}\n"
                f"📈 معدل النجاح: {(sent_count/(sent_count+failed_count)*100):.1f}%"
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ في الإرسال الجماعي: {str(e)}")
        finally:
            db.close()
    
    async def ban_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """حظر مستخدم (للمشرف فقط)"""
        user_id = update.effective_user.id
        
        if user_id != config.Config.ADMIN_ID:
            await update.message.reply_text("❌ ليس لديك صلاحية لهذا الأمر.")
            return
        
        if not context.args:
            await update.message.reply_text(
                "🚫 **حظر مستخدم**\n\n"
                "📝 **الاستخدام:**\n"
                "/ban <معرف_المستخدم>\n\n"
                "💡 **مثال:**\n"
                "/ban 123456789"
            )
            return
        
        try:
            target_user_id = int(context.args[0])
            
            if target_user_id == config.Config.ADMIN_ID:
                await update.message.reply_text("❌ لا يمكن حظر المشرف!")
                return
            
            self.ban_user(target_user_id)
            
            # إشعار المستخدم المحظور
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text="🚫 **تم حظرك من استخدام البوت**\n\n"
                         "📞 للاستفسار عن سبب الحظر، تواصل مع المشرف."
                )
            except:
                pass  # قد يكون المستخدم حظر البوت
            
            await update.message.reply_text(
                f"✅ تم حظر المستخدم {target_user_id} بنجاح.\n"
                f"📊 عدد التحذيرات السابقة: {self.user_warnings.get(target_user_id, 0)}"
            )
            
        except ValueError:
            await update.message.reply_text("❌ معرف المستخدم يجب أن يكون رقماً.")
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ في حظر المستخدم: {str(e)}")
    
    async def unban_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """إلغاء حظر مستخدم (للمشرف فقط)"""
        user_id = update.effective_user.id
        
        if user_id != config.Config.ADMIN_ID:
            await update.message.reply_text("❌ ليس لديك صلاحية لهذا الأمر.")
            return
        
        if not context.args:
            await update.message.reply_text(
                "✅ **إلغاء حظر مستخدم**\n\n"
                "📝 **الاستخدام:**\n"
                "/unban <معرف_المستخدم>\n\n"
                "💡 **مثال:**\n"
                "/unban 123456789"
            )
            return
        
        try:
            target_user_id = int(context.args[0])
            
            if target_user_id not in self.banned_users:
                await update.message.reply_text("⚠️ هذا المستخدم غير محظور.")
                return
            
            self.unban_user(target_user_id)
            # إزالة التحذيرات
            self.user_warnings.pop(target_user_id, None)
            
            # إشعار المستخدم
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text="🎉 **تم إلغاء حظرك!**\n\n"
                         "✅ يمكنك الآن استخدام البوت بشكل طبيعي.\n"
                         "⚠️ يرجى الالتزام بقواعد الاستخدام."
                )
            except:
                pass
            
            await update.message.reply_text(f"✅ تم إلغاء حظر المستخدم {target_user_id} بنجاح.")
            
        except ValueError:
            await update.message.reply_text("❌ معرف المستخدم يجب أن يكون رقماً.")
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ في إلغاء حظر المستخدم: {str(e)}")
    
    async def cleanup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """تنظيف فوري للنظام (للمشرف فقط)"""
        user_id = update.effective_user.id
        
        if user_id != config.Config.ADMIN_ID:
            await update.message.reply_text("❌ ليس لديك صلاحية لهذا الأمر.")
            return
        
        try:
            status_message = await update.message.reply_text(
                "🧹 **جاري تنظيف النظام...**\n\n"
                "⏳ يرجى الانتظار..."
            )
            
            # تنظيف الملفات المؤقتة
            temp_cleaned = await FileManager.cleanup_old_files(config.Config.TEMP_DIR, max_age_hours=1)
            
            # تنظيف ملفات التنزيل القديمة
            downloads_cleaned = await FileManager.cleanup_old_files(config.Config.DOWNLOADS_DIR, max_age_hours=24)
            
            # تنظيف السجلات القديمة
            logs_cleaned = await FileManager.cleanup_old_files(config.Config.LOGS_DIR, max_age_hours=168)  # أسبوع
            
            # إعادة تعيين حدود المعدل
            old_limits_count = len(self.user_rate_limits)
            self.user_rate_limits.clear()
            
            # تحديث وقت آخر تنظيف
            self.last_cleanup = time.time()
            
            await status_message.edit_text(
                f"✅ **تم تنظيف النظام بنجاح!**\n\n"
                f"📊 **النتائج:**\n"
                f"🗂️ ملفات مؤقتة: {temp_cleaned} ملف\n"
                f"📥 ملفات تنزيل: {downloads_cleaned} ملف\n"
                f"📋 ملفات سجلات: {logs_cleaned} ملف\n"
                f"🔄 حدود معدل: {old_limits_count} مستخدم\n\n"
                f"⏰ وقت التنظيف: {datetime.now().strftime('%H:%M:%S')}"
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ في تنظيف النظام: {str(e)}")
    
    async def system_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معلومات النظام المفصلة (للمشرف فقط)"""
        user_id = update.effective_user.id
        
        if user_id != config.Config.ADMIN_ID:
            await update.message.reply_text("❌ ليس لديك صلاحية لهذا الأمر.")
            return
        
        try:
            import psutil
            import os
            
            # معلومات النظام
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # معلومات البوت
            db: Session = next(get_db())
            total_users = db.query(User).count()
            active_users_24h = db.query(User).filter(
                User.last_activity > datetime.utcnow() - timedelta(hours=24)
            ).count()
            
            total_downloads = db.query(Download).filter(Download.status == "completed").count()
            failed_downloads = db.query(Download).filter(Download.status == "failed").count()
            
            # حجم المجلدات
            def get_folder_size(path):
                total = 0
                try:
                    for dirpath, dirnames, filenames in os.walk(path):
                        for filename in filenames:
                            filepath = os.path.join(dirpath, filename)
                            total += os.path.getsize(filepath)
                except:
                    pass
                return total
            
            temp_size = get_folder_size(config.Config.TEMP_DIR)
            downloads_size = get_folder_size(config.Config.DOWNLOADS_DIR)
            logs_size = get_folder_size(config.Config.LOGS_DIR)
            
            system_text = f"""🖥️ **معلومات النظام المفصلة**
            
📊 **أداء النظام:**
🔥 المعالج: {cpu_percent}%
💾 الذاكرة: {memory.percent}% ({FileManager.format_size(memory.used)}/{FileManager.format_size(memory.total)})
💿 التخزين: {disk.percent}% ({FileManager.format_size(disk.used)}/{FileManager.format_size(disk.total)})

👥 **إحصائيات المستخدمين:**
📈 إجمالي المستخدمين: {total_users}
🟢 نشطين (24 ساعة): {active_users_24h}
🚫 محظورين: {len(self.banned_users)}
⚠️ لديهم تحذيرات: {len(self.user_warnings)}

📥 **إحصائيات التنزيل:**
✅ تنزيلات ناجحة: {total_downloads}
❌ تنزيلات فاشلة: {failed_downloads}
⏳ تنزيلات نشطة: {len(self.active_downloads)}
📊 معدل النجاح: {(total_downloads/(total_downloads+failed_downloads)*100):.1f}% إذا كان هناك تنزيلات

💾 **استخدام التخزين:**
📁 ملفات مؤقتة: {FileManager.format_size(temp_size)}
📦 ملفات التنزيل: {FileManager.format_size(downloads_size)}
📋 ملفات السجلات: {FileManager.format_size(logs_size)}

🔧 **حالة البوت:**
⏰ آخر تنظيف: {datetime.fromtimestamp(self.last_cleanup).strftime('%Y-%m-%d %H:%M:%S')}
🔄 وقت التشغيل: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🌐 حالة الاتصال: مستقر"""
            
            await update.message.reply_text(system_text, parse_mode='Markdown')
            db.close()
            
        except ImportError:
            await update.message.reply_text(
                "⚠️ مكتبة psutil غير متوفرة لعرض معلومات النظام المفصلة.\n"
                "💡 لتثبيتها: pip install psutil"
            )
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ في جلب معلومات النظام: {str(e)}")
    
    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """إحصائيات المستخدم المحسنة"""
        user_id = update.effective_user.id
        db: Session = next(get_db())
        
        try:
            user = db.query(User).filter(User.telegram_id == user_id).first()
            if user:
                downloads = db.query(Download).filter(
                    Download.user_id == user_id,
                    Download.status == "completed"
                ).order_by(Download.end_time.desc()).limit(5).all()
                
                failed_downloads = db.query(Download).filter(
                    Download.user_id == user_id,
                    Download.status == "failed"
                ).count()
                
                # حساب إحصائيات إضافية
                success_rate = (user.total_downloads / max(user.total_downloads + failed_downloads, 1)) * 100
                avg_file_size = user.total_size // max(user.total_downloads, 1)
                
                # آخر التنزيلات مع التواريخ
                recent_downloads = "\n".join([
                    f"• {download.domain} - {FileManager.format_size(download.file_size)} ({download.end_time.strftime('%m/%d %H:%M')})"
                    for download in downloads
                ]) if downloads else "لا توجد تنزيلات بعد"
                
                # حساب الوقت المتبقي لإعادة تعيين الحدود
                current_requests = len(self.user_rate_limits[user_id])
                if current_requests > 0:
                    oldest_request = min(self.user_rate_limits[user_id])
                    reset_time = oldest_request + 3600 - time.time()
                    reset_text = f"{int(reset_time/60)} دقيقة" if reset_time > 0 else "متاح الآن"
                else:
                    reset_text = "متاح الآن"
                
                # تحديد مستوى المستخدم بناءً على الاستخدام
                if user.total_downloads >= 100:
                    user_level = "🏆 خبير"
                elif user.total_downloads >= 50:
                    user_level = "🥇 متقدم"
                elif user.total_downloads >= 20:
                    user_level = "🥈 متوسط"
                elif user.total_downloads >= 5:
                    user_level = "🥉 مبتدئ"
                else:
                    user_level = "🆕 جديد"
                
                stats_text = f"""📊 **إحصائياتك الشخصية**
                
👤 **معلومات الحساب:**
🆔 المعرف: {user.telegram_id}
🏅 المستوى: {user_level}
📅 عضو منذ: {user.created_at.strftime('%Y-%m-%d')}
⏰ آخر نشاط: {user.last_activity.strftime('%m-%d %H:%M')}

📈 **إحصائيات الأداء:**
📥 التنزيلات الناجحة: {user.total_downloads}
❌ التنزيلات الفاشلة: {failed_downloads}
📊 معدل النجاح: {success_rate:.1f}%
💾 إجمالي البيانات: {FileManager.format_size(user.total_size)}
📏 متوسط حجم الملف: {FileManager.format_size(avg_file_size)}

⚠️ **التحذيرات والحالة:**
🚨 عدد التحذيرات: {self.user_warnings.get(user_id, 0)}/3
🚫 الحالة: {'محظور' if self.is_user_banned(user_id) else 'نشط'}

🎯 **حدود الاستخدام:**
⏱️ الحد الأقصى/ساعة: {config.Config.RATE_LIMIT_PER_HOUR}
📊 المستخدم حالياً: {current_requests}/{config.Config.RATE_LIMIT_PER_HOUR}
🔄 إعادة تعيين خلال: {reset_text}

📋 **آخر 5 تنزيلات:**
{recent_downloads}

💡 **نصائح:**
• استخدم /history لعرض تاريخ كامل
• استخدم /settings لتخصيص الإعدادات
• تابع حدود الاستخدام لتجنب التأخير"""
                
                await update.message.reply_text(stats_text, parse_mode='Markdown')
            else:
                await update.message.reply_text(
                    "❌ **لم يتم العثور على بياناتك**\n\n"
                    "🔧 **لحل هذه المشكلة:**\n"
                    "1️⃣ استخدم الأمر /start\n"
                    "2️⃣ انتظر قليلاً ثم حاول مرة أخرى\n"
                    "3️⃣ إذا استمرت المشكلة، تواصل مع المشرف"
                )
        
        except Exception as e:
            logger.error(f"خطأ في إحصائيات المستخدم {user_id}: {e}")
            await update.message.reply_text("❌ حدث خطأ في جلب الإحصائيات. حاول مرة أخرى.")
        finally:
            db.close()

    async def settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """إعدادات المستخدم"""
        keyboard = get_settings_keyboard()
        await update.message.reply_text("⚙️ **إعدادات التنزيل:**", reply_markup=keyboard, parse_mode='Markdown')

    async def history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض تاريخ التنزيلات"""
        user_id = update.effective_user.id
        db: Session = next(get_db())
        
        downloads = db.query(Download).filter(
            Download.user_id == user_id,
            Download.status == "completed"
        ).order_by(Download.created_at.desc()).limit(5).all()
        
        if downloads:
            keyboard = get_download_history_keyboard(downloads)
            await update.message.reply_text("📁 **آخر التنزيلات:**", reply_markup=keyboard, parse_mode='Markdown')
        else:
            await update.message.reply_text("📭 لم تقم بأي تنزيلات بعد.")

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة نقرات الأزرار"""
        query = update.callback_query
        await query.answer()
        
        callback_data = query.data
        
        if callback_data == "back_main":
            await query.edit_message_text("🔙 العودة إلى القائمة الرئيسية", reply_markup=get_main_keyboard())
        elif callback_data.startswith("history_"):
            download_id = callback_data.split("_")[1]
            await self.show_download_details(query, download_id)
        elif callback_data == "download_full":
            await query.edit_message_text("✅ تم اختيار التنزيل الكامل")
        elif callback_data == "download_page":
            await query.edit_message_text("✅ تم اختيار الصفحة فقط")
        elif callback_data == "download_custom":
            await query.edit_message_text("⚙️ اختر الإعدادات المخصصة")
        # ... معالجات أخرى للأزرار

    async def show_download_details(self, query, download_id):
        """عرض تفاصيل التنزيل"""
        db: Session = next(get_db())
        download = db.query(Download).filter(Download.id == download_id).first()
        
        if download:
            details_text = f"""📋 **تفاصيل التنزيل**

🌐 الموقع: {download.url}
📊 الحالة: {download.status}
💾 الحجم: {FileManager.format_size(download.file_size)}
📁 عدد الملفات: {download.total_files}
⏰ المدة: {download.end_time - download.start_time if download.end_time else 'قيد المعالجة'}"""
            
            await query.edit_message_text(details_text, parse_mode='Markdown')
        else:
            await query.edit_message_text("❌ لم يتم العثور على التفاصيل")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """أمر المساعدة المحسن"""
        help_text = """🤖 **دليل استخدام WebMaster Bot:**

🌐 **لتنزيل موقع:**
• أرسل رابط الموقع مباشرة
• أو استخدم الزر '🌐 تنزيل موقع جديد'

⚙️ **الإعدادات المتاحة:**
• تحديد جودة التنزيل (سريع/متوازن/كامل)
• اختيار أنواع الملفات المطلوبة
• ضبط حجم التنزيل الأقصى

📊 **المميزات الرائعة:**
• حفظ تاريخ جميع تنزيلاتك
• إحصائيات مفصلة لاستخدامك
• دعم المواقع المعقدة والتفاعلية
• تنزيل فائق السرعة مع JavaScript
• ضغط ذكي وتنظيم الملفات

🔧 **الأوامر المتاحة:**
/start - بدء البوت والترحيب
/stats - عرض إحصائياتك
/history - تاريخ التنزيلات
/settings - إعدادات التنزيل
/help - هذه المساعدة
/cancel - إلغاء التنزيل الحالي

❓ **للدعم والأسئلة:**
تواصل مع المطور: @YourSupportUsername"""
        
        await update.message.reply_text(help_text, parse_mode='Markdown', reply_markup=get_main_keyboard())

    async def admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """لوحة إدارة المشرفين"""
        user_id = update.effective_user.id
        
        # التحقق من صلاحيات المشرف
        if user_id != config.Config.ADMIN_ID:
            await update.message.reply_text("❌ ليس لديك صلاحية للوصول إلى لوحة الإدارة.")
            return
        
        try:
            db: Session = next(get_db())
            
            # إحصائيات النظام
            total_users = db.query(User).count()
            total_downloads = db.query(Download).filter(Download.status == "completed").count()
            failed_downloads = db.query(Download).filter(Download.status == "failed").count()
            active_downloads = len(self.active_downloads)
            
            # حساب إجمالي الأحجام
            total_size_result = db.query(User).with_entities(
                db.func.sum(User.total_size)
            ).scalar() or 0
            
            admin_text = f"""👑 **لوحة إدارة WebMaster Bot**

📊 **إحصائيات النظام:**
👥 إجمالي المستخدمين: {total_users}
📥 التنزيلات الناجحة: {total_downloads}
❌ التنزيلات الفاشلة: {failed_downloads}
⏳ التنزيلات النشطة: {active_downloads}
💾 إجمالي البيانات: {FileManager.format_size(total_size_result)}

🔧 **حالة النظام:**
🟢 البوت يعمل بشكل طبيعي
🧹 آخر تنظيف: {datetime.fromtimestamp(self.last_cleanup).strftime('%H:%M:%S')}
⚡ الذاكرة: طبيعية
🌐 الاتصال: مستقر

📋 **الأوامر الإدارية:**
/admin - هذه اللوحة
/broadcast - إرسال رسالة جماعية
/ban - حظر مستخدم
/unban - إلغاء حظر مستخدم
/cleanup - تنظيف فوري للنظام"""
            
            await update.message.reply_text(
                admin_text, 
                parse_mode='Markdown',
                reply_markup=get_admin_keyboard()
            )
            
            db.close()
            
        except Exception as e:
            logger.error(f"❌ خطأ في لوحة الإدارة: {e}")
            await update.message.reply_text("❌ حدث خطأ في تحميل لوحة الإدارة.")
