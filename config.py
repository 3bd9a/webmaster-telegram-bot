import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """إعدادات البوت الرئيسية"""
    
    # إعدادات البوت الأساسية
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
    
    # إعدادات التنزيل
    MAX_CONCURRENT_DOWNLOADS = int(os.getenv("MAX_CONCURRENT_DOWNLOADS", 3))
    MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 50 * 1024 * 1024))  # 50MB
    MAX_WEBSITE_SIZE = int(os.getenv("MAX_WEBSITE_SIZE", 100 * 1024 * 1024))  # 100MB
    DOWNLOAD_TIMEOUT = int(os.getenv("DOWNLOAD_TIMEOUT", 300))  # 5 دقائق
    
    # إعدادات الأمان والحدود
    RATE_LIMIT_PER_HOUR = int(os.getenv("RATE_LIMIT_PER_HOUR", 10))
    ALLOWED_DOMAINS = os.getenv("ALLOWED_DOMAINS", "").split(",") if os.getenv("ALLOWED_DOMAINS") else []
    
    # إعدادات قاعدة البيانات
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/database.db")
    
    # إعدادات المجلدات
    DATA_DIR = os.getenv("DATA_DIR", "data")
    DOWNLOADS_DIR = os.path.join(DATA_DIR, "downloads")
    TEMP_DIR = os.path.join(DATA_DIR, "temp")
    LOGS_DIR = os.path.join(DATA_DIR, "logs")
    
    # إعدادات متقدمة
    DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    CLEANUP_INTERVAL = int(os.getenv("CLEANUP_INTERVAL", 3600))  # ساعة واحدة
    
    # إنشاء المجلدات المطلوبة
    @classmethod
    def create_directories(cls):
        """إنشاء جميع المجلدات المطلوبة"""
        directories = [cls.DATA_DIR, cls.DOWNLOADS_DIR, cls.TEMP_DIR, cls.LOGS_DIR]
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
