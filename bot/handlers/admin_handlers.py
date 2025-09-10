"""
معالجات الإدارة والمشرفين
Admin and Management Handlers
"""

import psutil
import os
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes

from .base_handler import BaseHandler
from bot.keyboards import get_admin_keyboard, get_confirmation_keyboard, get_main_keyboard
from utils.logger import logger
from database import get_db, Download, User
import config

class AdminHandlers(BaseHandler):
    """معالجات الإدارة والمشرفين"""
    
    def __init__(self, parent):
        super().__init__(parent)
    
    async def initialize(self):
        """تهيئة معالجات الإدارة"""
        logger.info("✅ تم تهيئة معالجات الإدارة")
    
    async def cleanup(self):
        """تنظيف موارد معالجات الإدارة"""
        logger.info("✅ تم تنظيف معالجات الإدارة")
    
    def _is_admin(self, user_id: int) -> bool:
        """فحص صلاحيات المشرف"""
        return user_id == config.Config.ADMIN_ID
    
    async def admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """لوحة تحكم المشرف"""
        user_id = update.effective_user.id
        
        if not self._is_admin(user_id):
            await update.message.reply_text(
                "🚫 **غير مصرح لك بالوصول**\n\n"
                "هذا الأمر مخصص للمشرفين فقط."
            )
            return
        
        try:
            # جمع إحصائيات سريعة
            db = next(get_db())
            
            total_users = db.query(User).count()
            total_downloads = db.query(Download).count()
            active_downloads = len(self.active_downloads)
            banned_users_count = len(self.banned_users)
            
            # إحصائيات اليوم
            today = datetime.utcnow().date()
            today_downloads = db.query(Download).filter(
                Download.created_at >= today
            ).count()
            
            db.close()
            
            admin_text = f"""🛡️ **لوحة تحكم المشرف**

📊 **إحصائيات عامة:**
👥 إجمالي المستخدمين: {total_users}
📥 إجمالي التنزيلات: {total_downloads}
📈 تنزيلات اليوم: {today_downloads}
⏳ تنزيلات نشطة: {active_downloads}
🚫 مستخدمين محظورين: {banned_users_count}

🖥️ **حالة النظام:**
💾 استخدام الذاكرة: {psutil.virtual_memory().percent:.1f}%
💽 استخدام القرص: {psutil.disk_usage('/').percent:.1f}%
⚡ حمولة المعالج: {psutil.cpu_percent():.1f}%

🕐 **آخر تنظيف:** {datetime.fromtimestamp(self.last_cleanup).strftime('%H:%M:%S')}

اختر العملية المطلوبة:"""
            
            await update.message.reply_text(
                admin_text,
                parse_mode='Markdown',
                reply_markup=get_admin_keyboard()
            )
            
        except Exception as e:
            logger.error(f"❌ خطأ في لوحة المشرف: {e}")
            await update.message.reply_text(
                "❌ حدث خطأ في تحميل لوحة التحكم"
            )
    
    async def broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """إرسال رسالة جماعية"""
        user_id = update.effective_user.id
        
        if not self._is_admin(user_id):
            await update.message.reply_text("🚫 غير مصرح لك بهذا الأمر")
            return
        
        # فحص إذا كان هناك نص للإرسال
        if not context.args:
            await update.message.reply_text(
                "📢 **إرسال رسالة جماعية**\n\n"
                "📝 الاستخدام: `/broadcast رسالتك هنا`\n\n"
                "💡 مثال: `/broadcast تحديث جديد للبوت متاح الآن!`"
            )
            return
        
        message_text = ' '.join(context.args)
        
        try:
            # جلب جميع المستخدمين
            db = next(get_db())
            users = db.query(User).all()
            db.close()
            
            sent_count = 0
            failed_count = 0
            
            broadcast_text = f"📢 **رسالة من إدارة البوت**\n\n{message_text}"
            
            # إرسال للجميع
            for user in users:
                try:
                    await context.bot.send_message(
                        chat_id=user.telegram_id,
                        text=broadcast_text,
                        parse_mode='Markdown'
                    )
                    sent_count += 1
                except Exception as e:
                    failed_count += 1
                    logger.warning(f"فشل إرسال لـ {user.telegram_id}: {e}")
            
            # تقرير النتائج
            result_text = f"✅ **تم إرسال الرسالة الجماعية**\n\n"
            result_text += f"📤 تم الإرسال لـ: {sent_count} مستخدم\n"
            result_text += f"❌ فشل الإرسال لـ: {failed_count} مستخدم\n"
            result_text += f"📊 معدل النجاح: {(sent_count/(sent_count+failed_count)*100):.1f}%"
            
            await update.message.reply_text(result_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"❌ خطأ في الإرسال الجماعي: {e}")
            await update.message.reply_text("❌ حدث خطأ في الإرسال الجماعي")
    
    async def ban_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """حظر مستخدم"""
        user_id = update.effective_user.id
        
        if not self._is_admin(user_id):
            await update.message.reply_text("🚫 غير مصرح لك بهذا الأمر")
            return
        
        if not context.args:
            await update.message.reply_text(
                "🚫 **حظر مستخدم**\n\n"
                "📝 الاستخدام: `/ban معرف_المستخدم`\n\n"
                "💡 مثال: `/ban 123456789`"
            )
            return
        
        try:
            target_user_id = int(context.args[0])
            
            if target_user_id == config.Config.ADMIN_ID:
                await update.message.reply_text("❌ لا يمكن حظر المشرف!")
                return
            
            self.ban_user(target_user_id)
            
            await update.message.reply_text(
                f"✅ **تم حظر المستخدم**\n\n"
                f"🆔 معرف المستخدم: `{target_user_id}`\n"
                f"⏰ وقت الحظر: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            # إشعار المستخدم المحظور
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text="🚫 **تم حظرك من استخدام البوت**\n\n"
                         "📞 للاستفسار، تواصل مع المشرف"
                )
            except:
                pass  # المستخدم قد يكون حظر البوت
                
        except ValueError:
            await update.message.reply_text("❌ معرف المستخدم يجب أن يكون رقماً")
        except Exception as e:
            logger.error(f"❌ خطأ في حظر المستخدم: {e}")
            await update.message.reply_text("❌ حدث خطأ في حظر المستخدم")
    
    async def unban_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """إلغاء حظر مستخدم"""
        user_id = update.effective_user.id
        
        if not self._is_admin(user_id):
            await update.message.reply_text("🚫 غير مصرح لك بهذا الأمر")
            return
        
        if not context.args:
            await update.message.reply_text(
                "✅ **إلغاء حظر مستخدم**\n\n"
                "📝 الاستخدام: `/unban معرف_المستخدم`\n\n"
                "💡 مثال: `/unban 123456789`"
            )
            return
        
        try:
            target_user_id = int(context.args[0])
            
            if target_user_id not in self.banned_users:
                await update.message.reply_text("❌ هذا المستخدم غير محظور")
                return
            
            self.unban_user(target_user_id)
            
            await update.message.reply_text(
                f"✅ **تم إلغاء حظر المستخدم**\n\n"
                f"🆔 معرف المستخدم: `{target_user_id}`\n"
                f"⏰ وقت إلغاء الحظر: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            # إشعار المستخدم
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text="🎉 **تم إلغاء حظرك من البوت**\n\n"
                         "✅ يمكنك الآن استخدام البوت بشكل طبيعي\n"
                         "🤝 نتمنى لك تجربة ممتعة!"
                )
            except:
                pass
                
        except ValueError:
            await update.message.reply_text("❌ معرف المستخدم يجب أن يكون رقماً")
        except Exception as e:
            logger.error(f"❌ خطأ في إلغاء حظر المستخدم: {e}")
            await update.message.reply_text("❌ حدث خطأ في إلغاء حظر المستخدم")
    
    async def cleanup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """تنظيف فوري للنظام"""
        user_id = update.effective_user.id
        
        if not self._is_admin(user_id):
            await update.message.reply_text("🚫 غير مصرح لك بهذا الأمر")
            return
        
        try:
            await update.message.reply_text("🧹 **بدء التنظيف الفوري...**")
            
            # تنظيف دوري
            await self.periodic_cleanup()
            
            # إحصائيات التنظيف
            temp_files = len([f for f in os.listdir(config.Config.TEMP_DIR) if os.path.isfile(os.path.join(config.Config.TEMP_DIR, f))])
            download_files = len([f for f in os.listdir(config.Config.DOWNLOADS_DIR) if os.path.isfile(os.path.join(config.Config.DOWNLOADS_DIR, f))])
            
            cleanup_text = f"✅ **تم التنظيف بنجاح**\n\n"
            cleanup_text += f"📁 ملفات مؤقتة متبقية: {temp_files}\n"
            cleanup_text += f"📥 ملفات تنزيل متبقية: {download_files}\n"
            cleanup_text += f"🧹 آخر تنظيف: {datetime.now().strftime('%H:%M:%S')}\n\n"
            cleanup_text += f"💾 استخدام الذاكرة: {psutil.virtual_memory().percent:.1f}%\n"
            cleanup_text += f"💽 استخدام القرص: {psutil.disk_usage('/').percent:.1f}%"
            
            await update.message.reply_text(cleanup_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"❌ خطأ في التنظيف: {e}")
            await update.message.reply_text("❌ حدث خطأ في التنظيف")
    
    async def system_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معلومات النظام المفصلة"""
        user_id = update.effective_user.id
        
        if not self._is_admin(user_id):
            await update.message.reply_text("🚫 غير مصرح لك بهذا الأمر")
            return
        
        try:
            # معلومات النظام
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # معلومات قاعدة البيانات
            db = next(get_db())
            total_users = db.query(User).count()
            total_downloads = db.query(Download).count()
            successful_downloads = db.query(Download).filter(Download.status == 'completed').count()
            failed_downloads = db.query(Download).filter(Download.status == 'failed').count()
            
            # إحصائيات الأسبوع الماضي
            week_ago = datetime.utcnow() - timedelta(days=7)
            week_downloads = db.query(Download).filter(Download.created_at >= week_ago).count()
            week_users = db.query(User).filter(User.created_at >= week_ago).count()
            
            db.close()
            
            # معدل النجاح
            success_rate = (successful_downloads / total_downloads * 100) if total_downloads > 0 else 0
            
            system_text = f"""🖥️ **معلومات النظام المفصلة**

💻 **الأجهزة:**
🧠 المعالج: {cpu_percent:.1f}%
💾 الذاكرة: {memory.percent:.1f}% ({memory.used // (1024**3):.1f}GB / {memory.total // (1024**3):.1f}GB)
💽 القرص: {disk.percent:.1f}% ({disk.used // (1024**3):.1f}GB / {disk.total // (1024**3):.1f}GB)

📊 **قاعدة البيانات:**
👥 إجمالي المستخدمين: {total_users}
📥 إجمالي التنزيلات: {total_downloads}
✅ تنزيلات ناجحة: {successful_downloads}
❌ تنزيلات فاشلة: {failed_downloads}
📈 معدل النجاح: {success_rate:.1f}%

📅 **إحصائيات الأسبوع:**
👤 مستخدمين جدد: {week_users}
📥 تنزيلات جديدة: {week_downloads}

🔧 **حالة البوت:**
⏳ تنزيلات نشطة: {len(self.active_downloads)}
🚫 مستخدمين محظورين: {len(self.banned_users)}
⚠️ تحذيرات نشطة: {len(self.user_warnings)}

🕐 **آخر تنظيف:** {datetime.fromtimestamp(self.last_cleanup).strftime('%Y-%m-%d %H:%M:%S')}"""
            
            await update.message.reply_text(system_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"❌ خطأ في معلومات النظام: {e}")
            await update.message.reply_text("❌ حدث خطأ في جلب معلومات النظام")
