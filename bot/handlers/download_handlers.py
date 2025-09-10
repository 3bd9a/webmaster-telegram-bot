"""
معالجات التنزيل والملفات
Download and File Handlers
"""

import asyncio
import os
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

from .base_handler import BaseHandler
from utils.helpers import sanitize_filename, get_domain_from_url, human_readable_size
from bot.keyboards import get_cancel_keyboard, get_main_keyboard
from utils.logger import logger
from database import get_db, Download
import config

class DownloadHandlers(BaseHandler):
    """معالجات التنزيل والملفات"""
    
    def __init__(self, parent):
        super().__init__(parent)
    
    async def initialize(self):
        """تهيئة معالجات التنزيل"""
        logger.info("✅ تم تهيئة معالجات التنزيل")
    
    async def cleanup(self):
        """تنظيف موارد معالجات التنزيل"""
        logger.info("✅ تم تنظيف معالجات التنزيل")
    
    async def handle_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
        """معالجة رابط للتنزيل"""
        user_id = update.effective_user.id
        
        # فحص أمان الرابط
        is_safe, safety_message = self.validate_url_security(url)
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
                    "⚠️ تحذير: تم رصد طلبات متكررة. يرجى الانتظار قبل طلب تنزيل آخر."
                )
                return
        
        # فحص حدود المعدل
        if not self.check_rate_limit(user_id):
            await update.message.reply_text(
                f"⏳ **تم تجاوز الحد المسموح**\n\n"
                f"🔢 الحد الأقصى: {config.Config.RATE_LIMIT_PER_HOUR} تنزيلات في الساعة\n"
                f"⏰ يرجى الانتظار قبل طلب تنزيل جديد"
            )
            return
        
        # فحص التنزيلات النشطة
        if user_id in self.active_downloads:
            await update.message.reply_text(
                "⏳ **لديك تنزيل نشط بالفعل**\n\n"
                "🔄 يرجى انتظار انتهاء التنزيل الحالي أو إلغاؤه أولاً\n"
                "💡 استخدم /cancel لإلغاء التنزيل الحالي"
            )
            return
        
        # بدء التنزيل
        await self.start_download(update, context, url)
    
    async def start_download(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
        """بدء عملية التنزيل"""
        user_id = update.effective_user.id
        domain = get_domain_from_url(url)
        
        try:
            # إنشاء سجل في قاعدة البيانات
            db = next(get_db())
            download_record = Download(
                user_id=user_id,
                url=url,
                domain=domain,
                status='in_progress',
                created_at=datetime.utcnow()
            )
            db.add(download_record)
            db.commit()
            download_id = download_record.id
            db.close()
            
            # إضافة للتنزيلات النشطة
            self.active_downloads[user_id] = {
                'download_id': download_id,
                'url': url,
                'domain': domain,
                'start_time': datetime.utcnow(),
                'status': 'starting'
            }
            
            # رسالة بدء التنزيل
            progress_message = await update.message.reply_text(
                f"🚀 **بدء تنزيل الموقع**\n\n"
                f"🌐 **الموقع:** {domain}\n"
                f"📊 **الحالة:** جاري التحضير...\n"
                f"⏰ **بدء في:** {datetime.now().strftime('%H:%M:%S')}\n\n"
                f"⏳ يرجى الانتظار، قد تستغرق العملية عدة دقائق...",
                parse_mode='Markdown',
                reply_markup=get_cancel_keyboard()
            )
            
            # حفظ معرف الرسالة للتحديث
            self.active_downloads[user_id]['message_id'] = progress_message.message_id
            
            # بدء التنزيل في مهمة منفصلة
            asyncio.create_task(self._download_website(update, context, url, download_id))
            
        except Exception as e:
            logger.error(f"❌ خطأ في بدء التنزيل: {e}")
            await update.message.reply_text(
                "❌ **حدث خطأ في بدء التنزيل**\n\n"
                "🔄 يرجى المحاولة مرة أخرى لاحقاً"
            )
            # تنظيف التنزيل الفاشل
            self.active_downloads.pop(user_id, None)
    
    async def _download_website(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, download_id: int):
        """تنزيل الموقع الفعلي"""
        user_id = update.effective_user.id
        
        try:
            # تحديث الحالة
            await self._update_progress(context, user_id, "🔍 جاري فحص الموقع...")
            
            # تنزيل الموقع
            result = await self.downloader.download_website(
                url=url,
                output_dir=config.Config.DOWNLOADS_DIR,
                progress_callback=lambda msg: asyncio.create_task(
                    self._update_progress(context, user_id, msg)
                )
            )
            
            if result['success']:
                # نجح التنزيل
                await self._handle_successful_download(update, context, result, download_id)
            else:
                # فشل التنزيل
                await self._handle_failed_download(update, context, result['error'], download_id)
                
        except asyncio.CancelledError:
            # تم إلغاء التنزيل
            await self._handle_cancelled_download(update, context, download_id)
        except Exception as e:
            logger.error(f"❌ خطأ في تنزيل الموقع: {e}")
            await self._handle_failed_download(update, context, str(e), download_id)
        finally:
            # تنظيف التنزيل النشط
            self.active_downloads.pop(user_id, None)
    
    async def _update_progress(self, context: ContextTypes.DEFAULT_TYPE, user_id: int, message: str):
        """تحديث رسالة التقدم"""
        try:
            if user_id in self.active_downloads:
                download_info = self.active_downloads[user_id]
                message_id = download_info.get('message_id')
                
                if message_id:
                    elapsed_time = datetime.utcnow() - download_info['start_time']
                    elapsed_str = f"{elapsed_time.seconds // 60}:{elapsed_time.seconds % 60:02d}"
                    
                    progress_text = f"🚀 **جاري تنزيل الموقع**\n\n"
                    progress_text += f"🌐 **الموقع:** {download_info['domain']}\n"
                    progress_text += f"📊 **الحالة:** {message}\n"
                    progress_text += f"⏱️ **الوقت المنقضي:** {elapsed_str}\n\n"
                    progress_text += f"⏳ يرجى الانتظار..."
                    
                    await context.bot.edit_message_text(
                        chat_id=user_id,
                        message_id=message_id,
                        text=progress_text,
                        parse_mode='Markdown',
                        reply_markup=get_cancel_keyboard()
                    )
        except Exception as e:
            logger.error(f"❌ خطأ في تحديث التقدم: {e}")
    
    async def _handle_successful_download(self, update: Update, context: ContextTypes.DEFAULT_TYPE, result: dict, download_id: int):
        """معالجة التنزيل الناجح"""
        user_id = update.effective_user.id
        
        try:
            # تحديث قاعدة البيانات
            db = next(get_db())
            download_record = db.query(Download).filter(Download.id == download_id).first()
            if download_record:
                download_record.status = 'completed'
                download_record.file_path = result['zip_path']
                download_record.file_size = result['total_size']
                download_record.completed_at = datetime.utcnow()
                db.commit()
            db.close()
            
            # إرسال الملف
            file_size = human_readable_size(result['total_size'])
            
            success_text = f"✅ **تم التنزيل بنجاح!**\n\n"
            success_text += f"🌐 **الموقع:** {result['domain']}\n"
            success_text += f"📁 **عدد الملفات:** {result['files_count']}\n"
            success_text += f"💾 **حجم الملف:** {file_size}\n"
            success_text += f"⏱️ **وقت التنزيل:** {result['duration']}\n\n"
            success_text += f"📎 **جاري إرسال الملف...**"
            
            # تحديث الرسالة
            message_id = self.active_downloads[user_id].get('message_id')
            if message_id:
                await context.bot.edit_message_text(
                    chat_id=user_id,
                    message_id=message_id,
                    text=success_text,
                    parse_mode='Markdown'
                )
            
            # إرسال الملف
            with open(result['zip_path'], 'rb') as file:
                await context.bot.send_document(
                    chat_id=user_id,
                    document=file,
                    filename=f"{result['domain']}.zip",
                    caption=f"🎉 **موقع {result['domain']} جاهز!**\n\n"
                           f"📱 يمكنك الآن فتح الملفات بدون إنترنت\n"
                           f"🔄 شكراً لاستخدام WebMaster Bot!",
                    parse_mode='Markdown',
                    reply_markup=get_main_keyboard()
                )
            
            # حذف الملف المؤقت
            try:
                os.remove(result['zip_path'])
            except:
                pass
                
        except Exception as e:
            logger.error(f"❌ خطأ في معالجة التنزيل الناجح: {e}")
            await update.message.reply_text(
                "✅ تم التنزيل بنجاح لكن حدث خطأ في الإرسال. يرجى المحاولة مرة أخرى."
            )
    
    async def _handle_failed_download(self, update: Update, context: ContextTypes.DEFAULT_TYPE, error: str, download_id: int):
        """معالجة التنزيل الفاشل"""
        user_id = update.effective_user.id
        
        try:
            # تحديث قاعدة البيانات
            db = next(get_db())
            download_record = db.query(Download).filter(Download.id == download_id).first()
            if download_record:
                download_record.status = 'failed'
                download_record.error_message = error
                download_record.completed_at = datetime.utcnow()
                db.commit()
            db.close()
            
            # رسالة الفشل
            error_text = f"❌ **فشل في التنزيل**\n\n"
            error_text += f"🌐 **الموقع:** {self.active_downloads[user_id]['domain']}\n"
            error_text += f"⚠️ **السبب:** {error}\n\n"
            error_text += f"💡 **اقتراحات:**\n"
            error_text += f"• تأكد من صحة الرابط\n"
            error_text += f"• جرب مرة أخرى لاحقاً\n"
            error_text += f"• تواصل مع المشرف إذا استمرت المشكلة"
            
            # تحديث الرسالة
            message_id = self.active_downloads[user_id].get('message_id')
            if message_id:
                await context.bot.edit_message_text(
                    chat_id=user_id,
                    message_id=message_id,
                    text=error_text,
                    parse_mode='Markdown',
                    reply_markup=get_main_keyboard()
                )
                
        except Exception as e:
            logger.error(f"❌ خطأ في معالجة التنزيل الفاشل: {e}")
    
    async def _handle_cancelled_download(self, update: Update, context: ContextTypes.DEFAULT_TYPE, download_id: int):
        """معالجة التنزيل المُلغى"""
        user_id = update.effective_user.id
        
        try:
            # تحديث قاعدة البيانات
            db = next(get_db())
            download_record = db.query(Download).filter(Download.id == download_id).first()
            if download_record:
                download_record.status = 'cancelled'
                download_record.completed_at = datetime.utcnow()
                db.commit()
            db.close()
            
            # رسالة الإلغاء
            cancel_text = f"🚫 **تم إلغاء التنزيل**\n\n"
            cancel_text += f"🌐 **الموقع:** {self.active_downloads[user_id]['domain']}\n"
            cancel_text += f"⏰ **تم الإلغاء في:** {datetime.now().strftime('%H:%M:%S')}\n\n"
            cancel_text += f"💡 يمكنك بدء تنزيل جديد في أي وقت"
            
            # تحديث الرسالة
            message_id = self.active_downloads[user_id].get('message_id')
            if message_id:
                await context.bot.edit_message_text(
                    chat_id=user_id,
                    message_id=message_id,
                    text=cancel_text,
                    parse_mode='Markdown',
                    reply_markup=get_main_keyboard()
                )
                
        except Exception as e:
            logger.error(f"❌ خطأ في معالجة التنزيل المُلغى: {e}")
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """إلغاء التنزيل الحالي"""
        user_id = update.effective_user.id
        
        if user_id not in self.active_downloads:
            await update.message.reply_text(
                "❌ **لا يوجد تنزيل نشط للإلغاء**\n\n"
                "💡 يمكنك بدء تنزيل جديد بإرسال رابط الموقع",
                reply_markup=get_main_keyboard()
            )
            return
        
        try:
            # إلغاء التنزيل
            download_info = self.active_downloads[user_id]
            download_id = download_info['download_id']
            
            # إشارة الإلغاء (سيتم التعامل معها في _download_website)
            await self._handle_cancelled_download(update, context, download_id)
            
            await update.message.reply_text(
                "✅ **تم إلغاء التنزيل بنجاح**\n\n"
                "🌐 يمكنك بدء تنزيل جديد الآن",
                reply_markup=get_main_keyboard()
            )
            
        except Exception as e:
            logger.error(f"❌ خطأ في إلغاء التنزيل: {e}")
            await update.message.reply_text(
                "❌ حدث خطأ في إلغاء التنزيل"
            )
