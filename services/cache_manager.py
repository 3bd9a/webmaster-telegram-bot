"""
نظام إدارة التخزين المؤقت المتقدم
Advanced Cache Management System
"""

import asyncio
import hashlib
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
import aiofiles

from utils.logger import logger
import config

class CacheManager:
    """مدير التخزين المؤقت المتقدم"""
    
    def __init__(self):
        self.cache_dir = Path(config.Config.DATA_DIR) / "cache"
        self.cache_dir.mkdir(exist_ok=True)
        
        # تخزين مؤقت في الذاكرة للوصول السريع
        self.memory_cache = {}
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'size': 0
        }
        
        # إعدادات التخزين المؤقت
        self.max_memory_cache_size = 100  # عدد العناصر
        self.default_ttl = 3600  # ساعة واحدة
        self.max_file_size = 10 * 1024 * 1024  # 10MB
    
    def _generate_cache_key(self, url: str, options: Dict = None) -> str:
        """إنشاء مفتاح تخزين مؤقت فريد"""
        cache_data = {
            'url': url,
            'options': options or {}
        }
        cache_string = json.dumps(cache_data, sort_keys=True)
        return hashlib.sha256(cache_string.encode()).hexdigest()[:16]
    
    def _get_cache_file_path(self, cache_key: str) -> Path:
        """الحصول على مسار ملف التخزين المؤقت"""
        return self.cache_dir / f"{cache_key}.json"
    
    def _get_data_file_path(self, cache_key: str) -> Path:
        """الحصول على مسار ملف البيانات"""
        return self.cache_dir / f"{cache_key}.zip"
    
    async def get(self, url: str, options: Dict = None) -> Optional[Dict]:
        """الحصول على عنصر من التخزين المؤقت"""
        cache_key = self._generate_cache_key(url, options)
        
        # فحص التخزين المؤقت في الذاكرة أولاً
        if cache_key in self.memory_cache:
            cache_item = self.memory_cache[cache_key]
            if self._is_cache_valid(cache_item):
                self.cache_stats['hits'] += 1
                logger.debug(f"🎯 Cache hit (memory): {cache_key}")
                return cache_item['data']
            else:
                # إزالة العنصر المنتهي الصلاحية
                del self.memory_cache[cache_key]
        
        # فحص التخزين المؤقت على القرص
        cache_file = self._get_cache_file_path(cache_key)
        if cache_file.exists():
            try:
                async with aiofiles.open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.loads(await f.read())
                
                if self._is_cache_valid(cache_data):
                    # إضافة للذاكرة للوصول السريع
                    self._add_to_memory_cache(cache_key, cache_data)
                    self.cache_stats['hits'] += 1
                    logger.debug(f"🎯 Cache hit (disk): {cache_key}")
                    return cache_data['data']
                else:
                    # حذف الملف المنتهي الصلاحية
                    await self._remove_cache_files(cache_key)
            
            except Exception as e:
                logger.error(f"❌ خطأ في قراءة التخزين المؤقت: {e}")
        
        self.cache_stats['misses'] += 1
        logger.debug(f"❌ Cache miss: {cache_key}")
        return None
    
    async def set(self, url: str, data: Dict, options: Dict = None, ttl: int = None) -> bool:
        """حفظ عنصر في التخزين المؤقت"""
        cache_key = self._generate_cache_key(url, options)
        ttl = ttl or self.default_ttl
        
        cache_item = {
            'data': data,
            'created_at': time.time(),
            'ttl': ttl,
            'url': url,
            'options': options or {}
        }
        
        try:
            # حفظ في الذاكرة
            self._add_to_memory_cache(cache_key, cache_item)
            
            # حفظ على القرص
            cache_file = self._get_cache_file_path(cache_key)
            async with aiofiles.open(cache_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(cache_item, indent=2))
            
            self.cache_stats['size'] += 1
            logger.debug(f"💾 Cache stored: {cache_key}")
            return True
            
        except Exception as e:
            logger.error(f"❌ خطأ في حفظ التخزين المؤقت: {e}")
            return False
    
    async def cache_file(self, cache_key: str, file_path: str) -> bool:
        """تخزين ملف في التخزين المؤقت"""
        try:
            if not os.path.exists(file_path):
                return False
            
            file_size = os.path.getsize(file_path)
            if file_size > self.max_file_size:
                logger.warning(f"⚠️ ملف كبير جداً للتخزين المؤقت: {human_readable_size(file_size)}")
                return False
            
            cached_file_path = self._get_data_file_path(cache_key)
            
            # نسخ الملف
            async with aiofiles.open(file_path, 'rb') as src:
                async with aiofiles.open(cached_file_path, 'wb') as dst:
                    await dst.write(await src.read())
            
            logger.debug(f"📁 File cached: {cache_key}")
            return True
            
        except Exception as e:
            logger.error(f"❌ خطأ في تخزين الملف: {e}")
            return False
    
    async def get_cached_file(self, cache_key: str) -> Optional[str]:
        """الحصول على ملف من التخزين المؤقت"""
        cached_file_path = self._get_data_file_path(cache_key)
        
        if cached_file_path.exists():
            return str(cached_file_path)
        
        return None
    
    def _is_cache_valid(self, cache_item: Dict) -> bool:
        """فحص صحة عنصر التخزين المؤقت"""
        if not cache_item:
            return False
        
        created_at = cache_item.get('created_at', 0)
        ttl = cache_item.get('ttl', self.default_ttl)
        
        return (time.time() - created_at) < ttl
    
    def _add_to_memory_cache(self, cache_key: str, cache_item: Dict):
        """إضافة عنصر للتخزين المؤقت في الذاكرة"""
        # إزالة العناصر القديمة إذا امتلأت الذاكرة
        if len(self.memory_cache) >= self.max_memory_cache_size:
            # إزالة أقدم عنصر
            oldest_key = min(
                self.memory_cache.keys(),
                key=lambda k: self.memory_cache[k].get('created_at', 0)
            )
            del self.memory_cache[oldest_key]
        
        self.memory_cache[cache_key] = cache_item
    
    async def _remove_cache_files(self, cache_key: str):
        """إزالة ملفات التخزين المؤقت"""
        try:
            cache_file = self._get_cache_file_path(cache_key)
            data_file = self._get_data_file_path(cache_key)
            
            if cache_file.exists():
                cache_file.unlink()
            
            if data_file.exists():
                data_file.unlink()
                
        except Exception as e:
            logger.error(f"❌ خطأ في حذف ملفات التخزين المؤقت: {e}")
    
    async def clear_expired(self):
        """مسح العناصر منتهية الصلاحية"""
        cleared_count = 0
        
        try:
            # مسح من الذاكرة
            expired_keys = []
            for key, item in self.memory_cache.items():
                if not self._is_cache_valid(item):
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self.memory_cache[key]
                cleared_count += 1
            
            # مسح من القرص
            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    async with aiofiles.open(cache_file, 'r', encoding='utf-8') as f:
                        cache_data = json.loads(await f.read())
                    
                    if not self._is_cache_valid(cache_data):
                        cache_key = cache_file.stem
                        await self._remove_cache_files(cache_key)
                        cleared_count += 1
                        
                except Exception as e:
                    logger.error(f"❌ خطأ في فحص ملف التخزين المؤقت: {e}")
            
            if cleared_count > 0:
                logger.info(f"🧹 تم مسح {cleared_count} عنصر منتهي الصلاحية من التخزين المؤقت")
                
        except Exception as e:
            logger.error(f"❌ خطأ في مسح التخزين المؤقت: {e}")
    
    async def clear_all(self):
        """مسح جميع عناصر التخزين المؤقت"""
        try:
            # مسح الذاكرة
            self.memory_cache.clear()
            
            # مسح الملفات
            for file_path in self.cache_dir.glob("*"):
                if file_path.is_file():
                    file_path.unlink()
            
            # إعادة تعيين الإحصائيات
            self.cache_stats = {
                'hits': 0,
                'misses': 0,
                'size': 0
            }
            
            logger.info("🧹 تم مسح جميع عناصر التخزين المؤقت")
            
        except Exception as e:
            logger.error(f"❌ خطأ في مسح التخزين المؤقت: {e}")
    
    def get_stats(self) -> Dict:
        """الحصول على إحصائيات التخزين المؤقت"""
        total_requests = self.cache_stats['hits'] + self.cache_stats['misses']
        hit_rate = (self.cache_stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'hits': self.cache_stats['hits'],
            'misses': self.cache_stats['misses'],
            'hit_rate': f"{hit_rate:.1f}%",
            'memory_cache_size': len(self.memory_cache),
            'disk_cache_size': len(list(self.cache_dir.glob("*.json"))),
            'total_size': self.cache_stats['size']
        }
    
    async def get_cache_size(self) -> Dict:
        """الحصول على حجم التخزين المؤقت"""
        try:
            total_size = 0
            file_count = 0
            
            for file_path in self.cache_dir.glob("*"):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
                    file_count += 1
            
            return {
                'total_size': total_size,
                'formatted_size': human_readable_size(total_size),
                'file_count': file_count
            }
            
        except Exception as e:
            logger.error(f"❌ خطأ في حساب حجم التخزين المؤقت: {e}")
            return {'total_size': 0, 'formatted_size': '0B', 'file_count': 0}

# إنشاء مثيل عام للاستخدام
cache_manager = CacheManager()
