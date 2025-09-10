import logging
import sys
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
from datetime import datetime

class CustomFormatter(logging.Formatter):
    """فورماتور مخصص للسجلات"""
    
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"

    FORMATS = {
        logging.DEBUG: grey + format + reset,
        logging.INFO: grey + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

def setup_logger(name="webmaster_bot", log_level=logging.INFO):
    """إعداد نظام السجلات"""
    # إنشاء المجلد إذا لم يكن موجوداً
    log_dir = "data/logs"
    os.makedirs(log_dir, exist_ok=True)
    
    # إنشاء الlogger
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    # منع تكرار السجلات
    if logger.hasHandlers():
        logger.handlers.clear()
    
    # معالج للconsole
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(CustomFormatter())
    
    # معالج للfile مع تدوير
    log_file = os.path.join(log_dir, f"bot_{datetime.now().strftime('%Y%m%d')}.log")
    file_handler = RotatingFileHandler(
        log_file, 
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s - [%(filename)s:%(lineno)d]'
    )
    file_handler.setFormatter(file_formatter)
    
    # إضافة المعالجات
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger

# إنشاء الlogger الرئيسي
logger = setup_logger()

def log_download_start(url, user_id):
    """تسجيل بدء التنزيل"""
    logger.info(f"📥 Download started - URL: {url} - User: {user_id}")

def log_download_complete(url, user_id, file_size, file_count):
    """تسجيل اكتمال التنزيل"""
    logger.info(f"✅ Download completed - URL: {url} - User: {user_id} - Size: {file_size} - Files: {file_count}")

def log_download_error(url, user_id, error):
    """تسجيل خطأ في التنزيل"""
    logger.error(f"❌ Download failed - URL: {url} - User: {user_id} - Error: {error}")

def log_user_action(user_id, action, details=""):
    """تسجيل عمل المستخدم"""
    logger.info(f"👤 User action - User: {user_id} - Action: {action} - Details: {details}")

def log_system_event(event, details=""):
    """تسجيل حدث نظام"""
    logger.info(f"⚡ System event - {event} - Details: {details}")

def log_performance_metric(metric_name, value):
    """تسجيل مقياس أداء"""
    logger.debug(f"📊 Performance - {metric_name}: {value}")
