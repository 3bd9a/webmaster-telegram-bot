"""
نظام إدارة قاعدة البيانات المتقدم
Advanced Database Management System
"""

import asyncio
import sqlite3
import aiosqlite
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, Text, JSON
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json
import os

from utils.logger import logger
import config

Base = declarative_base()

class User(Base):
    """جدول المستخدمين"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(255))
    first_name = Column(String(255))
    last_name = Column(String(255))
    language_code = Column(String(10), default='ar')
    is_banned = Column(Boolean, default=False)
    ban_reason = Column(Text)
    warnings_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)
    total_downloads = Column(Integer, default=0)
    successful_downloads = Column(Integer, default=0)
    failed_downloads = Column(Integer, default=0)
    settings = Column(JSON, default=dict)

class Download(Base):
    """جدول التنزيلات"""
    __tablename__ = 'downloads'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    url = Column(Text, nullable=False)
    status = Column(String(50), default='pending')  # pending, processing, completed, failed, cancelled
    file_path = Column(Text)
    file_size = Column(Integer, default=0)
    download_time = Column(Float, default=0.0)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    metadata = Column(JSON, default=dict)

class SystemLog(Base):
    """جدول سجلات النظام"""
    __tablename__ = 'system_logs'
    
    id = Column(Integer, primary_key=True)
    level = Column(String(20), nullable=False)  # INFO, WARNING, ERROR, CRITICAL
    message = Column(Text, nullable=False)
    module = Column(String(100))
    user_id = Column(Integer)
    timestamp = Column(DateTime, default=datetime.utcnow)
    metadata = Column(JSON, default=dict)

class SecurityEvent(Base):
    """جدول الأحداث الأمنية"""
    __tablename__ = 'security_events'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    event_type = Column(String(100), nullable=False)
    severity = Column(String(20), nullable=False)  # low, medium, high, critical
    description = Column(Text, nullable=False)
    ip_address = Column(String(45))
    user_agent = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    metadata = Column(JSON, default=dict)

class CacheEntry(Base):
    """جدول الكاش"""
    __tablename__ = 'cache_entries'
    
    id = Column(Integer, primary_key=True)
    key = Column(String(255), unique=True, nullable=False)
    value = Column(Text, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    access_count = Column(Integer, default=0)
    last_accessed = Column(DateTime, default=datetime.utcnow)

class DatabaseManager:
    """مدير قاعدة البيانات المتقدم"""
    
    def __init__(self):
        self.engine = None
        self.async_session = None
        self.connection_pool_size = 10
        self.max_overflow = 20
        self._initialized = False
    
    async def initialize(self):
        """تهيئة قاعدة البيانات"""
        try:
            # إنشاء محرك قاعدة البيانات
            database_url = config.Config.DATABASE_URL
            if database_url.startswith('sqlite'):
                # تحويل SQLite URL للاستخدام مع aiosqlite
                database_url = database_url.replace('sqlite:///', 'sqlite+aiosqlite:///')
            
            self.engine = create_async_engine(
                database_url,
                pool_size=self.connection_pool_size,
                max_overflow=self.max_overflow,
                pool_pre_ping=True,
                echo=config.Config.DEBUG_MODE
            )
            
            # إنشاء جلسة async
            self.async_session = sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # إنشاء الجداول
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            self._initialized = True
            logger.info("✅ تم تهيئة قاعدة البيانات بنجاح")
            
        except Exception as e:
            logger.error(f"❌ خطأ في تهيئة قاعدة البيانات: {e}")
            raise
    
    async def close(self):
        """إغلاق اتصالات قاعدة البيانات"""
        if self.engine:
            await self.engine.dispose()
        logger.info("✅ تم إغلاق اتصالات قاعدة البيانات")
    
    async def get_session(self) -> AsyncSession:
        """الحصول على جلسة قاعدة بيانات"""
        if not self._initialized:
            await self.initialize()
        return self.async_session()
    
    # === إدارة المستخدمين ===
    
    async def get_or_create_user(self, telegram_id: int, **kwargs) -> User:
        """الحصول على مستخدم أو إنشاؤه"""
        async with await self.get_session() as session:
            # البحث عن المستخدم
            result = await session.execute(
                "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
            )
            user_data = result.fetchone()
            
            if user_data:
                # تحديث آخر نشاط
                await session.execute(
                    "UPDATE users SET last_activity = ? WHERE telegram_id = ?",
                    (datetime.utcnow(), telegram_id)
                )
                await session.commit()
                
                # تحويل البيانات إلى كائن User
                user = User()
                for key, value in zip(user_data.keys(), user_data):
                    setattr(user, key, value)
                return user
            else:
                # إنشاء مستخدم جديد
                user_data = {
                    'telegram_id': telegram_id,
                    'username': kwargs.get('username'),
                    'first_name': kwargs.get('first_name'),
                    'last_name': kwargs.get('last_name'),
                    'language_code': kwargs.get('language_code', 'ar'),
                    'created_at': datetime.utcnow(),
                    'last_activity': datetime.utcnow(),
                    'settings': json.dumps({})
                }
                
                await session.execute(
                    """INSERT INTO users (telegram_id, username, first_name, last_name, 
                       language_code, created_at, last_activity, settings) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    tuple(user_data.values())
                )
                await session.commit()
                
                # إرجاع المستخدم الجديد
                user = User()
                for key, value in user_data.items():
                    setattr(user, key, value)
                return user
    
    async def update_user(self, telegram_id: int, **kwargs):
        """تحديث بيانات المستخدم"""
        async with await self.get_session() as session:
            set_clause = ", ".join([f"{key} = ?" for key in kwargs.keys()])
            values = list(kwargs.values()) + [telegram_id]
            
            await session.execute(
                f"UPDATE users SET {set_clause} WHERE telegram_id = ?",
                values
            )
            await session.commit()
    
    async def ban_user(self, telegram_id: int, reason: str = ""):
        """حظر مستخدم"""
        await self.update_user(
            telegram_id,
            is_banned=True,
            ban_reason=reason
        )
        logger.info(f"🚫 تم حظر المستخدم {telegram_id}: {reason}")
    
    async def unban_user(self, telegram_id: int):
        """إلغاء حظر مستخدم"""
        await self.update_user(
            telegram_id,
            is_banned=False,
            ban_reason=None
        )
        logger.info(f"✅ تم إلغاء حظر المستخدم {telegram_id}")
    
    async def add_user_warning(self, telegram_id: int, reason: str = ""):
        """إضافة تحذير للمستخدم"""
        async with await self.get_session() as session:
            # زيادة عدد التحذيرات
            await session.execute(
                "UPDATE users SET warnings_count = warnings_count + 1 WHERE telegram_id = ?",
                (telegram_id,)
            )
            
            # الحصول على عدد التحذيرات الحالي
            result = await session.execute(
                "SELECT warnings_count FROM users WHERE telegram_id = ?",
                (telegram_id,)
            )
            warnings_count = result.fetchone()[0]
            
            await session.commit()
            
            # حظر تلقائي بعد 3 تحذيرات
            if warnings_count >= 3:
                await self.ban_user(telegram_id, f"تجاوز حد التحذيرات: {reason}")
            
            return warnings_count
    
    async def get_user_stats(self, telegram_id: int) -> Dict:
        """الحصول على إحصائيات المستخدم"""
        async with await self.get_session() as session:
            # بيانات المستخدم
            user_result = await session.execute(
                "SELECT * FROM users WHERE telegram_id = ?",
                (telegram_id,)
            )
            user_data = user_result.fetchone()
            
            if not user_data:
                return {}
            
            # إحصائيات التنزيلات
            download_result = await session.execute(
                """SELECT 
                   COUNT(*) as total,
                   SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as successful,
                   SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                   AVG(download_time) as avg_time,
                   SUM(file_size) as total_size
                   FROM downloads WHERE user_id = ?""",
                (telegram_id,)
            )
            download_stats = download_result.fetchone()
            
            return {
                'user_info': dict(zip(user_data.keys(), user_data)),
                'download_stats': dict(zip(download_stats.keys(), download_stats)) if download_stats else {}
            }
    
    # === إدارة التنزيلات ===
    
    async def create_download(self, user_id: int, url: str, **kwargs) -> int:
        """إنشاء سجل تنزيل جديد"""
        async with await self.get_session() as session:
            download_data = {
                'user_id': user_id,
                'url': url,
                'status': kwargs.get('status', 'pending'),
                'created_at': datetime.utcnow(),
                'metadata': json.dumps(kwargs.get('metadata', {}))
            }
            
            result = await session.execute(
                """INSERT INTO downloads (user_id, url, status, created_at, metadata) 
                   VALUES (?, ?, ?, ?, ?)""",
                tuple(download_data.values())
            )
            
            download_id = result.lastrowid
            await session.commit()
            
            return download_id
    
    async def update_download(self, download_id: int, **kwargs):
        """تحديث سجل التنزيل"""
        async with await self.get_session() as session:
            # معالجة خاصة للـ metadata
            if 'metadata' in kwargs:
                kwargs['metadata'] = json.dumps(kwargs['metadata'])
            
            set_clause = ", ".join([f"{key} = ?" for key in kwargs.keys()])
            values = list(kwargs.values()) + [download_id]
            
            await session.execute(
                f"UPDATE downloads SET {set_clause} WHERE id = ?",
                values
            )
            await session.commit()
    
    async def get_user_downloads(self, user_id: int, limit: int = 10) -> List[Dict]:
        """الحصول على تنزيلات المستخدم"""
        async with await self.get_session() as session:
            result = await session.execute(
                """SELECT * FROM downloads WHERE user_id = ? 
                   ORDER BY created_at DESC LIMIT ?""",
                (user_id, limit)
            )
            
            downloads = []
            for row in result.fetchall():
                download = dict(zip(row.keys(), row))
                if download.get('metadata'):
                    download['metadata'] = json.loads(download['metadata'])
                downloads.append(download)
            
            return downloads
    
    async def get_download_stats(self) -> Dict:
        """الحصول على إحصائيات التنزيلات العامة"""
        async with await self.get_session() as session:
            result = await session.execute(
                """SELECT 
                   COUNT(*) as total,
                   SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as successful,
                   SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                   SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                   AVG(download_time) as avg_time,
                   SUM(file_size) as total_size
                   FROM downloads"""
            )
            
            stats = result.fetchone()
            return dict(zip(stats.keys(), stats)) if stats else {}
    
    # === إدارة السجلات ===
    
    async def log_event(self, level: str, message: str, module: str = None, 
                       user_id: int = None, **metadata):
        """تسجيل حدث في قاعدة البيانات"""
        async with await self.get_session() as session:
            await session.execute(
                """INSERT INTO system_logs (level, message, module, user_id, timestamp, metadata) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (level, message, module, user_id, datetime.utcnow(), json.dumps(metadata))
            )
            await session.commit()
    
    async def log_security_event(self, user_id: int, event_type: str, severity: str,
                                description: str, **kwargs):
        """تسجيل حدث أمني"""
        async with await self.get_session() as session:
            await session.execute(
                """INSERT INTO security_events 
                   (user_id, event_type, severity, description, ip_address, user_agent, timestamp, metadata) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, event_type, severity, description,
                 kwargs.get('ip_address'), kwargs.get('user_agent'),
                 datetime.utcnow(), json.dumps(kwargs.get('metadata', {})))
            )
            await session.commit()
    
    async def get_recent_logs(self, level: str = None, limit: int = 100) -> List[Dict]:
        """الحصول على السجلات الحديثة"""
        async with await self.get_session() as session:
            query = "SELECT * FROM system_logs"
            params = []
            
            if level:
                query += " WHERE level = ?"
                params.append(level)
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            result = await session.execute(query, params)
            
            logs = []
            for row in result.fetchall():
                log = dict(zip(row.keys(), row))
                if log.get('metadata'):
                    log['metadata'] = json.loads(log['metadata'])
                logs.append(log)
            
            return logs
    
    # === إدارة الكاش ===
    
    async def set_cache(self, key: str, value: str, ttl: int = 3600):
        """حفظ قيمة في الكاش"""
        async with await self.get_session() as session:
            expires_at = datetime.utcnow() + timedelta(seconds=ttl)
            
            # محاولة التحديث أولاً
            result = await session.execute(
                """UPDATE cache_entries SET value = ?, expires_at = ?, access_count = 0, last_accessed = ?
                   WHERE key = ?""",
                (value, expires_at, datetime.utcnow(), key)
            )
            
            # إذا لم يتم التحديث، أدخل سجل جديد
            if result.rowcount == 0:
                await session.execute(
                    """INSERT INTO cache_entries (key, value, expires_at, created_at, last_accessed) 
                       VALUES (?, ?, ?, ?, ?)""",
                    (key, value, expires_at, datetime.utcnow(), datetime.utcnow())
                )
            
            await session.commit()
    
    async def get_cache(self, key: str) -> Optional[str]:
        """الحصول على قيمة من الكاش"""
        async with await self.get_session() as session:
            result = await session.execute(
                "SELECT value, expires_at FROM cache_entries WHERE key = ?",
                (key,)
            )
            
            row = result.fetchone()
            if not row:
                return None
            
            value, expires_at = row
            
            # فحص انتهاء الصلاحية
            if datetime.utcnow() > expires_at:
                await session.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                await session.commit()
                return None
            
            # تحديث عداد الوصول
            await session.execute(
                "UPDATE cache_entries SET access_count = access_count + 1, last_accessed = ? WHERE key = ?",
                (datetime.utcnow(), key)
            )
            await session.commit()
            
            return value
    
    async def delete_cache(self, key: str):
        """حذف قيمة من الكاش"""
        async with await self.get_session() as session:
            await session.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
            await session.commit()
    
    async def cleanup_expired_cache(self):
        """تنظيف الكاش المنتهي الصلاحية"""
        async with await self.get_session() as session:
            result = await session.execute(
                "DELETE FROM cache_entries WHERE expires_at < ?",
                (datetime.utcnow(),)
            )
            deleted_count = result.rowcount
            await session.commit()
            
            if deleted_count > 0:
                logger.info(f"🧹 تم حذف {deleted_count} عنصر منتهي الصلاحية من الكاش")
    
    # === إدارة النظام ===
    
    async def get_system_stats(self) -> Dict:
        """الحصول على إحصائيات النظام"""
        async with await self.get_session() as session:
            stats = {}
            
            # إحصائيات المستخدمين
            user_result = await session.execute(
                """SELECT 
                   COUNT(*) as total_users,
                   SUM(CASE WHEN is_banned = 1 THEN 1 ELSE 0 END) as banned_users,
                   SUM(CASE WHEN last_activity > datetime('now', '-1 day') THEN 1 ELSE 0 END) as active_24h
                   FROM users"""
            )
            stats['users'] = dict(zip(user_result.fetchone().keys(), user_result.fetchone()))
            
            # إحصائيات التنزيلات
            download_result = await session.execute(
                """SELECT 
                   COUNT(*) as total_downloads,
                   SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as successful,
                   SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                   AVG(download_time) as avg_time
                   FROM downloads"""
            )
            stats['downloads'] = dict(zip(download_result.fetchone().keys(), download_result.fetchone()))
            
            # إحصائيات الأمان
            security_result = await session.execute(
                """SELECT 
                   COUNT(*) as total_events,
                   SUM(CASE WHEN severity = 'critical' THEN 1 ELSE 0 END) as critical_events,
                   SUM(CASE WHEN timestamp > datetime('now', '-1 day') THEN 1 ELSE 0 END) as recent_events
                   FROM security_events"""
            )
            stats['security'] = dict(zip(security_result.fetchone().keys(), security_result.fetchone()))
            
            return stats
    
    async def cleanup_old_data(self, days: int = 30):
        """تنظيف البيانات القديمة"""
        async with await self.get_session() as session:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # حذف السجلات القديمة
            logs_result = await session.execute(
                "DELETE FROM system_logs WHERE timestamp < ?",
                (cutoff_date,)
            )
            
            # حذف الأحداث الأمنية القديمة
            security_result = await session.execute(
                "DELETE FROM security_events WHERE timestamp < ?",
                (cutoff_date,)
            )
            
            # حذف التنزيلات القديمة المكتملة
            downloads_result = await session.execute(
                "DELETE FROM downloads WHERE completed_at < ? AND status = 'completed'",
                (cutoff_date,)
            )
            
            await session.commit()
            
            logger.info(f"🧹 تم تنظيف البيانات القديمة: "
                       f"{logs_result.rowcount} سجل، "
                       f"{security_result.rowcount} حدث أمني، "
                       f"{downloads_result.rowcount} تنزيل")
    
    async def backup_database(self, backup_path: str):
        """نسخ احتياطي لقاعدة البيانات"""
        try:
            if config.Config.DATABASE_URL.startswith('sqlite'):
                # نسخ احتياطي لـ SQLite
                db_path = config.Config.DATABASE_URL.replace('sqlite:///', '')
                
                async with aiosqlite.connect(db_path) as source:
                    async with aiosqlite.connect(backup_path) as backup:
                        await source.backup(backup)
                
                logger.info(f"✅ تم إنشاء نسخة احتياطية: {backup_path}")
            else:
                logger.warning("⚠️ النسخ الاحتياطي متاح فقط لـ SQLite")
                
        except Exception as e:
            logger.error(f"❌ خطأ في النسخ الاحتياطي: {e}")
            raise

# إنشاء مثيل عام للاستخدام
db_manager = DatabaseManager()
