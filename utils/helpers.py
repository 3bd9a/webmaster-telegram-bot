import re
import os
import hashlib
from urllib.parse import urlparse, urljoin
from datetime import datetime
import magic
import aiofiles
from pathlib import Path

def is_valid_url(url):
    """التحقق من صحة الرابط"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def sanitize_filename(filename):
    """تنظيف اسم الملف من الأحغير غير الآمنة"""
    # إزالة الأحغير غير المسموحة
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # إزالة المسافات من البداية والنهاية
    filename = filename.strip()
    # تقليل الطول إذا كان طويلاً
    if len(filename) > 100:
        name, ext = os.path.splitext(filename)
        filename = name[:95] + ext
    return filename

def get_domain_from_url(url):
    """استخراج النطاق من الرابط"""
    try:
        return urlparse(url).netloc
    except:
        return "unknown"

def generate_unique_id():
    """إنشاء معرف فريد"""
    return hashlib.md5(datetime.now().isoformat().encode()).hexdigest()[:8]

def is_same_domain(url1, url2):
    """التحقق إذا كان الرابطين من نفس النطاق"""
    try:
        domain1 = urlparse(url1).netloc
        domain2 = urlparse(url2).netloc
        return domain1 == domain2
    except:
        return False

def get_file_extension(filename):
    """الحصول على امتداد الملف"""
    return os.path.splitext(filename)[1].lower()

def is_supported_file(url):
    """التحقق إذا كان الملف مدعوماً للتنزيل"""
    supported_extensions = {
        '.html', '.htm', '.css', '.js', '.json',
        '.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.ico',
        '.woff', '.woff2', '.ttf', '.otf', '.eot',
        '.mp4', '.webm', '.ogg', '.mp3', '.wav'
    }
    ext = get_file_extension(url)
    return ext in supported_extensions

async def detect_file_type(file_path):
    """كشف نوع الملف باستخدام magic"""
    try:
        mime = magic.Magic(mime=True)
        file_type = mime.from_file(file_path)
        return file_type
    except:
        return "application/octet-stream"

def format_timedelta(delta):
    """تنسيق الفارق الزمني"""
    total_seconds = int(delta.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"

def human_readable_size(size_bytes):
    """تحويل الحجم إلى صيغة مقروءة"""
    if size_bytes == 0:
        return "0B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {units[i]}"

def is_large_file(size_bytes, threshold=10*1024*1024):
    """التحقق إذا كان الملف كبيراً"""
    return size_bytes > threshold

def create_directory_structure(base_path, structure):
    """إنشاء هيكل مجلدات"""
    for folder in structure:
        path = os.path.join(base_path, folder)
        os.makedirs(path, exist_ok=True)

def cleanup_old_files(directory, max_age_hours=24):
    """تنظيف الملفات القديمة"""
    now = datetime.now()
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        if os.path.isfile(file_path):
            file_time = datetime.fromtimestamp(os.path.getctime(file_path))
            if (now - file_time).total_seconds() > max_age_hours * 3600:
                os.remove(file_path)
