"""
الفئة الأساسية لجميع معالجات البوت
Base Handler Class for All Bot Handlers
"""

import asyncio
import time
from typing import Dict, Optional
from collections import defaultdict
from datetime import datetime

from services.downloader import WebsiteDownloader
from services.file_manager import FileManager
from utils.logger import logger
from database import get_db, Download, User
import config

class BaseHandler:
    """الفئة الأساسية لجميع المعالجات"""
    
    def __init__(self, parent=None):
        self.parent = parent
        if not parent:  # إذا كانت هذه الفئة الرئيسية
            self.downloader = WebsiteDownloader()
            self.active_downloads = {}
            self.user_rate_limits = defaultdict(list)
            self.banned_users = set()
            self.user_warnings = defaultdict(int)
            self.suspicious_activity = defaultdict(list)
            self.last_cleanup = time.time()
        else:
            # استخدام الموارد من الفئة الأب
            self.downloader = parent.downloader
            self.active_downloads = parent.active_downloads
            self.user_rate_limits = parent.user_rate_limits
            self.banned_users = parent.banned_users
            self.user_warnings = parent.user_warnings
            self.suspicious_activity = parent.suspicious_activity
            self.last_cleanup = parent.last_cleanup
    
    async def initialize(self):
        """تهيئة الموارد الأساسية"""
        if not self.parent:  # فقط للفئة الرئيسية
            try:
                await self.downloader.initialize()
                logger.info("✅ تم تهيئة محرك التنزيل بنجاح")
            except Exception as e:
                logger.error(f"❌ فشل في تهيئة محرك التنزيل: {e}")
                raise
    
    async def cleanup(self):
        """تنظيف الموارد الأساسية"""
        if not self.parent:  # فقط للفئة الرئيسية
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
    
    async def save_user_to_db(self, user):
        """حفظ بيانات المستخدم في قاعدة البيانات"""
        try:
            db = next(get_db())
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
            return db_user
            
        except Exception as e:
            logger.error(f"❌ خطأ في حفظ المستخدم: {e}")
            return None
