import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """إعدادات البوت الرئيسية"""
    
    # إعدادات البوت الأساسية
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
    
    # إعدادات التنزيل
    MAX_CONCURRENT_DOWNLOADS = int(os.getenv("MAX_CONCURRENT_DOWNLOADS", 3))  # تحسين التحميلات المتزامنة
    MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 20 * 1024 * 1024))  # 20MB
    MAX_WEBSITE_SIZE = int(os.getenv("MAX_WEBSITE_SIZE", 50 * 1024 * 1024))  # 50MB
    DOWNLOAD_TIMEOUT = int(os.getenv("DOWNLOAD_TIMEOUT", 300))  # 5 دقائق
    PAGE_LOAD_TIMEOUT = int(os.getenv("PAGE_LOAD_TIMEOUT", 60000))  # 60 ثانية
    NETWORK_IDLE_TIMEOUT = int(os.getenv("NETWORK_IDLE_TIMEOUT", 15000))  # 15 ثانية
    
    # إعدادات الذاكرة والأداء
    MAX_MEMORY_USAGE = int(os.getenv("MAX_MEMORY_USAGE", 512))  # MB بدلاً من نسبة مئوية
    MAX_CONTEXTS_POOL = int(os.getenv("MAX_CONTEXTS_POOL", 3))  # عدد السياقات في المجموعة
    
    # إعدادات الأمان والحدود
    RATE_LIMIT_PER_HOUR = int(os.getenv("RATE_LIMIT_PER_HOUR", 10))
    RATE_LIMIT_DOWNLOADS = int(os.getenv("RATE_LIMIT_DOWNLOADS", 5))  # تنزيلات في الساعة
    MAX_USER_QUEUE_SIZE = int(os.getenv("MAX_USER_QUEUE_SIZE", 5))  # حد قائمة انتظار المستخدم
    ALLOWED_DOMAINS = os.getenv("ALLOWED_DOMAINS", "").split(",") if os.getenv("ALLOWED_DOMAINS") else []
    ENABLE_EXTERNAL_SECURITY_CHECK = os.getenv("ENABLE_EXTERNAL_SECURITY_CHECK", "false").lower() == "true"
    
    # إعدادات قاعدة البيانات
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/database.db")
    
    # إعدادات المجلدات
    DATA_DIR = os.getenv("DATA_DIR", "data")
    DOWNLOADS_DIR = os.path.join(DATA_DIR, "downloads")
    TEMP_DIR = os.path.join(DATA_DIR, "temp")
    LOGS_DIR = os.path.join(DATA_DIR, "logs")
    CACHE_DIR = os.path.join(DATA_DIR, "cache")
    
    # إعدادات الكاش
    CACHE_TTL_DEFAULT = int(os.getenv("CACHE_TTL_DEFAULT", 3600))  # ساعة واحدة
    CACHE_MAX_SIZE = int(os.getenv("CACHE_MAX_SIZE", 100))  # عدد العناصر
    CACHE_CLEANUP_INTERVAL = int(os.getenv("CACHE_CLEANUP_INTERVAL", 1800))  # 30 دقيقة
    
    # إعدادات متقدمة
    DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    CLEANUP_INTERVAL = int(os.getenv("CLEANUP_INTERVAL", 3600))  # ساعة واحدة
    
    # إعدادات قوائل الانتظار
    QUEUE_MAX_RETRIES = int(os.getenv("QUEUE_MAX_RETRIES", 3))
    QUEUE_RETRY_DELAY = int(os.getenv("QUEUE_RETRY_DELAY", 5))  # ثواني
    
    # إعدادات المراقبة
    ENABLE_METRICS = os.getenv("ENABLE_METRICS", "true").lower() == "true"
    METRICS_PORT = int(os.getenv("METRICS_PORT", 8001))
    HEALTH_CHECK_PORT = int(os.getenv("HEALTH_CHECK_PORT", 8000))
    
    # إنشاء المجلدات المطلوبة
    @classmethod
    def create_directories(cls):
        """إنشاء جميع المجلدات المطلوبة"""
        directories = [cls.DATA_DIR, cls.DOWNLOADS_DIR, cls.TEMP_DIR, cls.LOGS_DIR, cls.CACHE_DIR]
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
    
    # التحقق من صحة الإعدادات
    @classmethod
    def validate(cls):
        """التحقق من صحة الإعدادات الأساسية"""
        if not cls.BOT_TOKEN:
            raise ValueError("❌ BOT_TOKEN غير محدد في ملف .env")
        if not cls.ADMIN_ID:
            raise ValueError("❌ ADMIN_ID غير محدد في ملف .env")
        
        cls.create_directories()
        return True

# تهيئة الإعدادات عند الاستيراد
Config.validate()
