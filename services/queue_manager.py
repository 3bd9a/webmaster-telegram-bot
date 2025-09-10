"""
نظام إدارة قوائم الانتظار المتقدم
Advanced Queue Management System
"""

import asyncio
import heapq
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
from dataclasses import dataclass, field
import uuid

from utils.logger import logger
import config

class Priority(Enum):
    """أولويات المهام"""
    LOW = 3
    NORMAL = 2
    HIGH = 1
    URGENT = 0

class TaskStatus(Enum):
    """حالات المهام"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class QueueTask:
    """مهمة في قائمة الانتظار"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: int = 0
    url: str = ""
    priority: Priority = Priority.NORMAL
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    callback: Optional[Callable] = None
    context: Dict[str, Any] = field(default_factory=dict)
    
    def __lt__(self, other):
        """للمقارنة في heap queue"""
        if self.priority.value != other.priority.value:
            return self.priority.value < other.priority.value
        return self.created_at < other.created_at

class DownloadQueue:
    """نظام قوائم الانتظار للتنزيلات"""
    
    def __init__(self, max_concurrent: int = None):
        self.max_concurrent = max_concurrent or config.Config.MAX_CONCURRENT_DOWNLOADS
        self.pending_queue = []  # heap queue للمهام المنتظرة
        self.running_tasks = {}  # المهام قيد التنفيذ
        self.completed_tasks = {}  # المهام المكتملة
        self.user_queues = {}  # قوائم انتظار المستخدمين
        self.queue_lock = asyncio.Lock()
        self.stats = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'cancelled_tasks': 0
        }
        
        # بدء معالج القائمة
        self._queue_processor_task = None
        self._is_running = False
    
    async def start(self):
        """بدء معالج القائمة"""
        if self._is_running:
            return
        
        self._is_running = True
        self._queue_processor_task = asyncio.create_task(self._process_queue())
        logger.info("🚀 تم بدء معالج قوائل الانتظار")
    
    async def stop(self):
        """إيقاف معالج القائمة"""
        self._is_running = False
        
        if self._queue_processor_task:
            self._queue_processor_task.cancel()
            try:
                await self._queue_processor_task
            except asyncio.CancelledError:
                pass
        
        # إلغاء جميع المهام قيد التنفيذ
        for task_id, task_info in self.running_tasks.items():
            if 'asyncio_task' in task_info:
                task_info['asyncio_task'].cancel()
        
        logger.info("⏹️ تم إيقاف معالج قوائل الانتظار")
    
    async def add_task(self, user_id: int, url: str, priority: Priority = Priority.NORMAL, 
                      callback: Callable = None, context: Dict = None) -> str:
        """إضافة مهمة جديدة للقائمة"""
        async with self.queue_lock:
            # فحص حدود المستخدم
            user_pending_count = self._get_user_pending_count(user_id)
            max_user_queue = 5  # حد أقصى 5 مهام لكل مستخدم
            
            if user_pending_count >= max_user_queue:
                raise Exception(f"تجاوز الحد الأقصى للمهام المنتظرة ({max_user_queue})")
            
            # إنشاء المهمة
            task = QueueTask(
                user_id=user_id,
                url=url,
                priority=priority,
                callback=callback,
                context=context or {}
            )
            
            # إضافة للقائمة
            heapq.heappush(self.pending_queue, task)
            
            # تحديث إحصائيات المستخدم
            if user_id not in self.user_queues:
                self.user_queues[user_id] = []
            self.user_queues[user_id].append(task.id)
            
            self.stats['total_tasks'] += 1
            
            logger.info(f"📝 تم إضافة مهمة جديدة: {task.id} للمستخدم {user_id}")
            return task.id
    
    async def cancel_task(self, task_id: str, user_id: int = None) -> bool:
        """إلغاء مهمة"""
        async with self.queue_lock:
            # البحث في المهام قيد التنفيذ
            if task_id in self.running_tasks:
                task_info = self.running_tasks[task_id]
                task = task_info['task']
                
                # فحص الصلاحية
                if user_id and task.user_id != user_id:
                    return False
                
                # إلغاء المهمة
                if 'asyncio_task' in task_info:
                    task_info['asyncio_task'].cancel()
                
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.utcnow()
                
                # نقل للمهام المكتملة
                self.completed_tasks[task_id] = task
                del self.running_tasks[task_id]
                
                self.stats['cancelled_tasks'] += 1
                logger.info(f"🚫 تم إلغاء المهمة: {task_id}")
                return True
            
            # البحث في المهام المنتظرة
            for i, task in enumerate(self.pending_queue):
                if task.id == task_id:
                    # فحص الصلاحية
                    if user_id and task.user_id != user_id:
                        return False
                    
                    # إزالة من القائمة
                    self.pending_queue.pop(i)
                    heapq.heapify(self.pending_queue)
                    
                    task.status = TaskStatus.CANCELLED
                    task.completed_at = datetime.utcnow()
                    self.completed_tasks[task_id] = task
                    
                    self.stats['cancelled_tasks'] += 1
                    logger.info(f"🚫 تم إلغاء المهمة المنتظرة: {task_id}")
                    return True
            
            return False
    
    async def get_task_status(self, task_id: str) -> Optional[QueueTask]:
        """الحصول على حالة المهمة"""
        # البحث في المهام قيد التنفيذ
        if task_id in self.running_tasks:
            return self.running_tasks[task_id]['task']
        
        # البحث في المهام المكتملة
        if task_id in self.completed_tasks:
            return self.completed_tasks[task_id]
        
        # البحث في المهام المنتظرة
        for task in self.pending_queue:
            if task.id == task_id:
                return task
        
        return None
    
    async def get_user_tasks(self, user_id: int) -> List[QueueTask]:
        """الحصول على مهام المستخدم"""
        user_tasks = []
        
        # المهام قيد التنفيذ
        for task_info in self.running_tasks.values():
            if task_info['task'].user_id == user_id:
                user_tasks.append(task_info['task'])
        
        # المهام المنتظرة
        for task in self.pending_queue:
            if task.user_id == user_id:
                user_tasks.append(task)
        
        # آخر 10 مهام مكتملة
        completed_user_tasks = [
            task for task in self.completed_tasks.values()
            if task.user_id == user_id
        ]
        completed_user_tasks.sort(key=lambda x: x.completed_at or x.created_at, reverse=True)
        user_tasks.extend(completed_user_tasks[:10])
        
        return user_tasks
    
    def get_queue_stats(self) -> Dict:
        """الحصول على إحصائيات القائمة"""
        return {
            'pending_tasks': len(self.pending_queue),
            'running_tasks': len(self.running_tasks),
            'completed_tasks': len(self.completed_tasks),
            'total_tasks': self.stats['total_tasks'],
            'success_rate': (
                self.stats['completed_tasks'] / max(1, self.stats['total_tasks']) * 100
            ),
            'max_concurrent': self.max_concurrent,
            'active_users': len(self.user_queues)
        }
    
    def _get_user_pending_count(self, user_id: int) -> int:
        """عدد المهام المنتظرة للمستخدم"""
        count = 0
        
        # المهام قيد التنفيذ
        for task_info in self.running_tasks.values():
            if task_info['task'].user_id == user_id:
                count += 1
        
        # المهام المنتظرة
        for task in self.pending_queue:
            if task.user_id == user_id:
                count += 1
        
        return count
    
    async def _process_queue(self):
        """معالج القائمة الرئيسي"""
        while self._is_running:
            try:
                await self._process_pending_tasks()
                await self._cleanup_completed_tasks()
                await asyncio.sleep(1)  # فحص كل ثانية
                
            except Exception as e:
                logger.error(f"❌ خطأ في معالج القائمة: {e}")
                await asyncio.sleep(5)
    
    async def _process_pending_tasks(self):
        """معالجة المهام المنتظرة"""
        async with self.queue_lock:
            # فحص إذا كان هناك مساحة للمهام الجديدة
            if len(self.running_tasks) >= self.max_concurrent:
                return
            
            # فحص إذا كان هناك مهام منتظرة
            if not self.pending_queue:
                return
            
            # أخذ المهمة التالية
            task = heapq.heappop(self.pending_queue)
            
            # بدء تنفيذ المهمة
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.utcnow()
            
            # إنشاء مهمة asyncio
            asyncio_task = asyncio.create_task(self._execute_task(task))
            
            self.running_tasks[task.id] = {
                'task': task,
                'asyncio_task': asyncio_task
            }
            
            logger.info(f"▶️ بدء تنفيذ المهمة: {task.id}")
    
    async def _execute_task(self, task: QueueTask):
        """تنفيذ مهمة واحدة"""
        try:
            if task.callback:
                # تنفيذ المهمة مع callback
                result = await task.callback(task)
                
                if result.get('success', False):
                    task.status = TaskStatus.COMPLETED
                    task.progress = 100.0
                    self.stats['completed_tasks'] += 1
                else:
                    raise Exception(result.get('error', 'Unknown error'))
            else:
                # مهمة افتراضية
                await asyncio.sleep(1)
                task.status = TaskStatus.COMPLETED
                task.progress = 100.0
                self.stats['completed_tasks'] += 1
            
        except asyncio.CancelledError:
            task.status = TaskStatus.CANCELLED
            self.stats['cancelled_tasks'] += 1
            logger.info(f"🚫 تم إلغاء المهمة: {task.id}")
            
        except Exception as e:
            task.error_message = str(e)
            task.retry_count += 1
            
            # إعادة المحاولة إذا لم نصل للحد الأقصى
            if task.retry_count <= task.max_retries:
                task.status = TaskStatus.PENDING
                task.started_at = None
                
                # إعادة إضافة للقائمة مع تأخير
                await asyncio.sleep(min(task.retry_count * 5, 30))  # تأخير متزايد
                async with self.queue_lock:
                    heapq.heappush(self.pending_queue, task)
                
                logger.warning(f"🔄 إعادة محاولة المهمة: {task.id} (المحاولة {task.retry_count})")
            else:
                task.status = TaskStatus.FAILED
                self.stats['failed_tasks'] += 1
                logger.error(f"❌ فشلت المهمة نهائياً: {task.id} - {e}")
        
        finally:
            task.completed_at = datetime.utcnow()
            
            # نقل للمهام المكتملة
            async with self.queue_lock:
                if task.id in self.running_tasks:
                    del self.running_tasks[task.id]
                self.completed_tasks[task.id] = task
    
    async def _cleanup_completed_tasks(self):
        """تنظيف المهام المكتملة القديمة"""
        if len(self.completed_tasks) <= 1000:  # احتفظ بآخر 1000 مهمة
            return
        
        # ترتيب حسب تاريخ الإكمال
        sorted_tasks = sorted(
            self.completed_tasks.items(),
            key=lambda x: x[1].completed_at or x[1].created_at
        )
        
        # حذف النصف الأقدم
        tasks_to_remove = sorted_tasks[:len(sorted_tasks)//2]
        
        async with self.queue_lock:
            for task_id, _ in tasks_to_remove:
                del self.completed_tasks[task_id]
        
        logger.info(f"🧹 تم تنظيف {len(tasks_to_remove)} مهمة قديمة")

# إنشاء مثيل عام للاستخدام
download_queue = DownloadQueue()
