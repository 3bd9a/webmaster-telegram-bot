import os
import zipfile
import aiofiles
import asyncio
from pathlib import Path
import shutil
import time
from datetime import datetime

# استيراد مطلق
from utils.logger import logger

class FileManager:
    @staticmethod
    async def create_zip(source_dir, output_path):
        """إنشاء ملف ZIP من المجلد"""
        try:
            def sync_zip():
                with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, dirs, files in os.walk(source_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, source_dir)
                            zipf.write(file_path, arcname)
            
            await asyncio.get_event_loop().run_in_executor(None, sync_zip)
            
            zip_size = os.path.getsize(output_path)
            return output_path, zip_size
            
        except Exception as e:
            logger.error(f"Error creating ZIP: {e}")
            raise
    
    @staticmethod
    async def cleanup_old_files(directory, max_age_hours=24):
        """تنظيف الملفات القديمة بشكل غير متزامن"""
        try:
            if not os.path.exists(directory):
                return
            
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            cleaned_count = 0
            cleaned_size = 0
            
            def cleanup_sync():
                nonlocal cleaned_count, cleaned_size
                for filename in os.listdir(directory):
                    file_path = os.path.join(directory, filename)
                    if os.path.isfile(file_path):
                        file_age = current_time - os.path.getctime(file_path)
                        if file_age > max_age_seconds:
                            file_size = os.path.getsize(file_path)
                            os.remove(file_path)
                            cleaned_count += 1
                            cleaned_size += file_size
                    elif os.path.isdir(file_path):
                        # تنظيف المجلدات الفارغة القديمة
                        try:
                            if not os.listdir(file_path):  # مجلد فارغ
                                dir_age = current_time - os.path.getctime(file_path)
                                if dir_age > max_age_seconds:
                                    os.rmdir(file_path)
                                    cleaned_count += 1
                        except OSError:
                            pass
            
            await asyncio.get_event_loop().run_in_executor(None, cleanup_sync)
            
            if cleaned_count > 0:
                logger.info(f"🧹 تم تنظيف {cleaned_count} ملف ({FileManager.format_size(cleaned_size)}) من {directory}")
            
            return cleaned_count, cleaned_size
            
        except Exception as e:
            logger.error(f"❌ خطأ في تنظيف الملفات من {directory}: {e}")
            return 0, 0
    
    @staticmethod
    async def cleanup_directory(directory_path, timeout=3600):
        """حذف المجلد بعد وقت محدد"""
        await asyncio.sleep(timeout)
        try:
            if os.path.exists(directory_path):
                shutil.rmtree(directory_path)
                logger.info(f"Cleaned up directory: {directory_path}")
        except Exception as e:
            logger.error(f"Error cleaning up directory: {e}")
    
    @staticmethod
    def get_file_size(file_path):
        """الحصول على حجم الملف"""
        return os.path.getsize(file_path)
    
    @staticmethod
    def format_size(size_bytes):
        """تنسيق حجم الملف"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"
