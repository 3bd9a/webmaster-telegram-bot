"""
نظام المراقبة والإحصائيات المتقدم
Advanced Monitoring and Statistics System
"""

import asyncio
import time
import psutil
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import threading
from prometheus_client import Counter, Histogram, Gauge, start_http_server
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

from utils.logger import logger
import config

@dataclass
class SystemMetrics:
    """مقاييس النظام"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    disk_usage_percent: float
    network_sent_mb: float
    network_recv_mb: float
    active_connections: int

@dataclass
class BotMetrics:
    """مقاييس البوت"""
    timestamp: datetime
    total_users: int
    active_users_24h: int
    total_downloads: int
    successful_downloads: int
    failed_downloads: int
    queue_size: int
    cache_hits: int
    cache_misses: int
    avg_download_time: float

class MetricsCollector:
    """جامع المقاييس والإحصائيات"""
    
    def __init__(self):
        self.system_metrics_history = deque(maxlen=1440)  # 24 ساعة بدقيقة واحدة
        self.bot_metrics_history = deque(maxlen=1440)
        self.user_activity = defaultdict(list)
        self.download_stats = defaultdict(int)
        self.error_counts = defaultdict(int)
        self.performance_metrics = defaultdict(list)
        
        # Prometheus metrics
        self.setup_prometheus_metrics()
        
        # بدء جمع المقاييس
        self._collection_task = None
        self._is_running = False
        
        # FastAPI app للواجهة
        self.app = FastAPI(title="WebMaster Bot Monitoring", version="1.0.0")
        self.setup_api_routes()
    
    def setup_prometheus_metrics(self):
        """إعداد مقاييس Prometheus"""
        self.prom_downloads_total = Counter('bot_downloads_total', 'Total downloads', ['status'])
        self.prom_download_duration = Histogram('bot_download_duration_seconds', 'Download duration')
        self.prom_active_users = Gauge('bot_active_users', 'Active users')
        self.prom_queue_size = Gauge('bot_queue_size', 'Queue size')
        self.prom_memory_usage = Gauge('bot_memory_usage_mb', 'Memory usage in MB')
        self.prom_cpu_usage = Gauge('bot_cpu_usage_percent', 'CPU usage percentage')
        self.prom_cache_hits = Counter('bot_cache_hits_total', 'Cache hits')
        self.prom_cache_misses = Counter('bot_cache_misses_total', 'Cache misses')
        self.prom_errors = Counter('bot_errors_total', 'Errors', ['type'])
    
    def setup_api_routes(self):
        """إعداد مسارات API"""
        
        @self.app.get("/")
        async def root():
            return {"message": "WebMaster Bot Monitoring API", "status": "running"}
        
        @self.app.get("/health")
        async def health_check():
            """فحص صحة النظام"""
            try:
                system_metrics = await self.get_current_system_metrics()
                bot_metrics = await self.get_current_bot_metrics()
                
                health_status = {
                    "status": "healthy",
                    "timestamp": datetime.utcnow().isoformat(),
                    "system": {
                        "cpu_ok": system_metrics.cpu_percent < 80,
                        "memory_ok": system_metrics.memory_percent < 85,
                        "disk_ok": system_metrics.disk_usage_percent < 90
                    },
                    "bot": {
                        "queue_ok": bot_metrics.queue_size < 50,
                        "error_rate_ok": self._calculate_error_rate() < 0.1
                    }
                }
                
                # تحديد الحالة العامة
                all_checks = [
                    health_status["system"]["cpu_ok"],
                    health_status["system"]["memory_ok"],
                    health_status["system"]["disk_ok"],
                    health_status["bot"]["queue_ok"],
                    health_status["bot"]["error_rate_ok"]
                ]
                
                if not all(all_checks):
                    health_status["status"] = "unhealthy"
                
                return JSONResponse(content=health_status)
                
            except Exception as e:
                logger.error(f"❌ خطأ في فحص الصحة: {e}")
                return JSONResponse(
                    content={"status": "error", "message": str(e)},
                    status_code=500
                )
        
        @self.app.get("/metrics/system")
        async def get_system_metrics():
            """الحصول على مقاييس النظام"""
            try:
                current = await self.get_current_system_metrics()
                history = list(self.system_metrics_history)[-60:]  # آخر ساعة
                
                return {
                    "current": asdict(current),
                    "history": [asdict(m) for m in history],
                    "summary": {
                        "avg_cpu": sum(m.cpu_percent for m in history) / len(history) if history else 0,
                        "avg_memory": sum(m.memory_percent for m in history) / len(history) if history else 0,
                        "peak_memory": max((m.memory_used_mb for m in history), default=0)
                    }
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/metrics/bot")
        async def get_bot_metrics():
            """الحصول على مقاييس البوت"""
            try:
                current = await self.get_current_bot_metrics()
                history = list(self.bot_metrics_history)[-60:]  # آخر ساعة
                
                return {
                    "current": asdict(current),
                    "history": [asdict(m) for m in history],
                    "download_stats": dict(self.download_stats),
                    "error_counts": dict(self.error_counts),
                    "top_errors": self._get_top_errors()
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/metrics/users")
        async def get_user_metrics():
            """الحصول على مقاييس المستخدمين"""
            try:
                now = datetime.utcnow()
                day_ago = now - timedelta(days=1)
                week_ago = now - timedelta(days=7)
                
                active_24h = len([
                    user_id for user_id, activities in self.user_activity.items()
                    if any(activity > day_ago for activity in activities)
                ])
                
                active_7d = len([
                    user_id for user_id, activities in self.user_activity.items()
                    if any(activity > week_ago for activity in activities)
                ])
                
                return {
                    "total_users": len(self.user_activity),
                    "active_24h": active_24h,
                    "active_7d": active_7d,
                    "user_activity_distribution": self._get_user_activity_distribution()
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/metrics/performance")
        async def get_performance_metrics():
            """الحصول على مقاييس الأداء"""
            try:
                return {
                    "download_times": {
                        "avg": self._calculate_avg_metric("download_time"),
                        "p95": self._calculate_percentile("download_time", 95),
                        "p99": self._calculate_percentile("download_time", 99)
                    },
                    "response_times": {
                        "avg": self._calculate_avg_metric("response_time"),
                        "p95": self._calculate_percentile("response_time", 95),
                        "p99": self._calculate_percentile("response_time", 99)
                    },
                    "cache_performance": {
                        "hit_rate": self._calculate_cache_hit_rate(),
                        "total_hits": self.download_stats.get("cache_hits", 0),
                        "total_misses": self.download_stats.get("cache_misses", 0)
                    }
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
    
    async def start(self):
        """بدء نظام المراقبة"""
        if self._is_running:
            return
        
        self._is_running = True
        
        # بدء Prometheus server
        if config.Config.ENABLE_METRICS:
            try:
                start_http_server(config.Config.METRICS_PORT)
                logger.info(f"🔍 تم بدء خادم Prometheus على المنفذ {config.Config.METRICS_PORT}")
            except Exception as e:
                logger.error(f"❌ خطأ في بدء خادم Prometheus: {e}")
        
        # بدء جمع المقاييس
        self._collection_task = asyncio.create_task(self._collect_metrics_loop())
        
        # بدء API server في thread منفصل
        self._start_api_server()
        
        logger.info("🚀 تم بدء نظام المراقبة")
    
    async def stop(self):
        """إيقاف نظام المراقبة"""
        self._is_running = False
        
        if self._collection_task:
            self._collection_task.cancel()
            try:
                await self._collection_task
            except asyncio.CancelledError:
                pass
        
        logger.info("⏹️ تم إيقاف نظام المراقبة")
    
    def _start_api_server(self):
        """بدء خادم API في thread منفصل"""
        def run_server():
            try:
                uvicorn.run(
                    self.app,
                    host="0.0.0.0",
                    port=config.Config.HEALTH_CHECK_PORT,
                    log_level="warning"
                )
            except Exception as e:
                logger.error(f"❌ خطأ في خادم API: {e}")
        
        api_thread = threading.Thread(target=run_server, daemon=True)
        api_thread.start()
        logger.info(f"🌐 تم بدء خادم API على المنفذ {config.Config.HEALTH_CHECK_PORT}")
    
    async def _collect_metrics_loop(self):
        """حلقة جمع المقاييس"""
        while self._is_running:
            try:
                # جمع مقاييس النظام
                system_metrics = await self.get_current_system_metrics()
                self.system_metrics_history.append(system_metrics)
                
                # جمع مقاييس البوت
                bot_metrics = await self.get_current_bot_metrics()
                self.bot_metrics_history.append(bot_metrics)
                
                # تحديث Prometheus metrics
                self._update_prometheus_metrics(system_metrics, bot_metrics)
                
                # تنظيف البيانات القديمة
                await self._cleanup_old_data()
                
                await asyncio.sleep(60)  # جمع كل دقيقة
                
            except Exception as e:
                logger.error(f"❌ خطأ في جمع المقاييس: {e}")
                await asyncio.sleep(60)
    
    async def get_current_system_metrics(self) -> SystemMetrics:
        """الحصول على مقاييس النظام الحالية"""
        try:
            # معلومات CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # معلومات الذاكرة
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used_mb = memory.used / 1024 / 1024
            
            # معلومات القرص
            disk = psutil.disk_usage('/')
            disk_usage_percent = disk.percent
            
            # معلومات الشبكة
            network = psutil.net_io_counters()
            network_sent_mb = network.bytes_sent / 1024 / 1024
            network_recv_mb = network.bytes_recv / 1024 / 1024
            
            # الاتصالات النشطة
            connections = len(psutil.net_connections())
            
            return SystemMetrics(
                timestamp=datetime.utcnow(),
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_used_mb=memory_used_mb,
                disk_usage_percent=disk_usage_percent,
                network_sent_mb=network_sent_mb,
                network_recv_mb=network_recv_mb,
                active_connections=connections
            )
            
        except Exception as e:
            logger.error(f"❌ خطأ في جمع مقاييس النظام: {e}")
            return SystemMetrics(
                timestamp=datetime.utcnow(),
                cpu_percent=0, memory_percent=0, memory_used_mb=0,
                disk_usage_percent=0, network_sent_mb=0, network_recv_mb=0,
                active_connections=0
            )
    
    async def get_current_bot_metrics(self) -> BotMetrics:
        """الحصول على مقاييس البوت الحالية"""
        try:
            # استيراد الخدمات المطلوبة
            from services.queue_manager import download_queue
            
            # إحصائيات المستخدمين
            total_users = len(self.user_activity)
            now = datetime.utcnow()
            day_ago = now - timedelta(days=1)
            
            active_users_24h = len([
                user_id for user_id, activities in self.user_activity.items()
                if any(activity > day_ago for activity in activities)
            ])
            
            # إحصائيات التنزيلات
            total_downloads = self.download_stats.get('total', 0)
            successful_downloads = self.download_stats.get('success', 0)
            failed_downloads = self.download_stats.get('failed', 0)
            
            # إحصائيات القائمة
            queue_stats = download_queue.get_queue_stats()
            queue_size = queue_stats.get('pending_tasks', 0)
            
            # إحصائيات الكاش
            cache_hits = self.download_stats.get('cache_hits', 0)
            cache_misses = self.download_stats.get('cache_misses', 0)
            
            # متوسط وقت التنزيل
            avg_download_time = self._calculate_avg_metric('download_time')
            
            return BotMetrics(
                timestamp=datetime.utcnow(),
                total_users=total_users,
                active_users_24h=active_users_24h,
                total_downloads=total_downloads,
                successful_downloads=successful_downloads,
                failed_downloads=failed_downloads,
                queue_size=queue_size,
                cache_hits=cache_hits,
                cache_misses=cache_misses,
                avg_download_time=avg_download_time
            )
            
        except Exception as e:
            logger.error(f"❌ خطأ في جمع مقاييس البوت: {e}")
            return BotMetrics(
                timestamp=datetime.utcnow(),
                total_users=0, active_users_24h=0, total_downloads=0,
                successful_downloads=0, failed_downloads=0, queue_size=0,
                cache_hits=0, cache_misses=0, avg_download_time=0.0
            )
    
    def _update_prometheus_metrics(self, system_metrics: SystemMetrics, bot_metrics: BotMetrics):
        """تحديث مقاييس Prometheus"""
        try:
            # مقاييس النظام
            self.prom_cpu_usage.set(system_metrics.cpu_percent)
            self.prom_memory_usage.set(system_metrics.memory_used_mb)
            
            # مقاييس البوت
            self.prom_active_users.set(bot_metrics.active_users_24h)
            self.prom_queue_size.set(bot_metrics.queue_size)
            
        except Exception as e:
            logger.error(f"❌ خطأ في تحديث Prometheus: {e}")
    
    def record_user_activity(self, user_id: int):
        """تسجيل نشاط المستخدم"""
        self.user_activity[user_id].append(datetime.utcnow())
        # الاحتفاظ بآخر 100 نشاط لكل مستخدم
        if len(self.user_activity[user_id]) > 100:
            self.user_activity[user_id] = self.user_activity[user_id][-100:]
    
    def record_download(self, status: str, duration: float = 0):
        """تسجيل عملية تنزيل"""
        self.download_stats['total'] += 1
        self.download_stats[status] += 1
        
        if duration > 0:
            self.performance_metrics['download_time'].append(duration)
            self.prom_download_duration.observe(duration)
        
        self.prom_downloads_total.labels(status=status).inc()
    
    def record_cache_hit(self):
        """تسجيل إصابة كاش"""
        self.download_stats['cache_hits'] += 1
        self.prom_cache_hits.inc()
    
    def record_cache_miss(self):
        """تسجيل فقدان كاش"""
        self.download_stats['cache_misses'] += 1
        self.prom_cache_misses.inc()
    
    def record_error(self, error_type: str, error_message: str = ""):
        """تسجيل خطأ"""
        self.error_counts[error_type] += 1
        self.prom_errors.labels(type=error_type).inc()
        
        # حفظ تفاصيل الخطأ
        error_key = f"{error_type}:{error_message[:50]}"
        self.error_counts[error_key] += 1
    
    def record_performance_metric(self, metric_name: str, value: float):
        """تسجيل مقياس أداء"""
        self.performance_metrics[metric_name].append(value)
        # الاحتفاظ بآخر 1000 قياس
        if len(self.performance_metrics[metric_name]) > 1000:
            self.performance_metrics[metric_name] = self.performance_metrics[metric_name][-1000:]
    
    def _calculate_avg_metric(self, metric_name: str) -> float:
        """حساب متوسط مقياس"""
        values = self.performance_metrics.get(metric_name, [])
        return sum(values) / len(values) if values else 0.0
    
    def _calculate_percentile(self, metric_name: str, percentile: int) -> float:
        """حساب النسبة المئوية لمقياس"""
        values = sorted(self.performance_metrics.get(metric_name, []))
        if not values:
            return 0.0
        
        index = int(len(values) * percentile / 100)
        return values[min(index, len(values) - 1)]
    
    def _calculate_cache_hit_rate(self) -> float:
        """حساب معدل إصابة الكاش"""
        hits = self.download_stats.get('cache_hits', 0)
        misses = self.download_stats.get('cache_misses', 0)
        total = hits + misses
        return (hits / total * 100) if total > 0 else 0.0
    
    def _calculate_error_rate(self) -> float:
        """حساب معدل الأخطاء"""
        total_downloads = self.download_stats.get('total', 0)
        failed_downloads = self.download_stats.get('failed', 0)
        return (failed_downloads / total_downloads) if total_downloads > 0 else 0.0
    
    def _get_top_errors(self, limit: int = 10) -> List[Dict]:
        """الحصول على أكثر الأخطاء شيوعاً"""
        sorted_errors = sorted(
            self.error_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return [
            {"error": error, "count": count}
            for error, count in sorted_errors[:limit]
        ]
    
    def _get_user_activity_distribution(self) -> Dict:
        """الحصول على توزيع نشاط المستخدمين"""
        now = datetime.utcnow()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(days=7)
        
        activity_counts = {
            "last_hour": 0,
            "last_day": 0,
            "last_week": 0
        }
        
        for activities in self.user_activity.values():
            if any(activity > hour_ago for activity in activities):
                activity_counts["last_hour"] += 1
            if any(activity > day_ago for activity in activities):
                activity_counts["last_day"] += 1
            if any(activity > week_ago for activity in activities):
                activity_counts["last_week"] += 1
        
        return activity_counts
    
    async def _cleanup_old_data(self):
        """تنظيف البيانات القديمة"""
        try:
            # تنظيف نشاط المستخدمين (أكثر من شهر)
            month_ago = datetime.utcnow() - timedelta(days=30)
            
            for user_id in list(self.user_activity.keys()):
                self.user_activity[user_id] = [
                    activity for activity in self.user_activity[user_id]
                    if activity > month_ago
                ]
                
                # حذف المستخدمين غير النشطين
                if not self.user_activity[user_id]:
                    del self.user_activity[user_id]
            
            # تنظيف مقاييس الأداء
            for metric_name in list(self.performance_metrics.keys()):
                if len(self.performance_metrics[metric_name]) > 1000:
                    self.performance_metrics[metric_name] = self.performance_metrics[metric_name][-1000:]
            
        except Exception as e:
            logger.error(f"❌ خطأ في تنظيف البيانات: {e}")

# إنشاء مثيل عام للاستخدام
metrics_collector = MetricsCollector()
