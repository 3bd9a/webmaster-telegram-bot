"""
اختبارات وحدة للمنزل
Unit Tests for Downloader
"""

import pytest
import asyncio
import tempfile
import os
from unittest.mock import Mock, patch, AsyncMock
from services.downloader import WebsiteDownloader
from services.cache_manager import cache_manager
from services.security_manager import security_manager
import config

class TestWebsiteDownloader:
    """اختبارات منزل المواقع"""
    
    @pytest.fixture
    async def downloader(self):
        """إنشاء مثيل منزل للاختبار"""
        downloader = WebsiteDownloader()
        await downloader.initialize()
        yield downloader
        await downloader.close()
    
    @pytest.fixture
    def temp_dir(self):
        """مجلد مؤقت للاختبار"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.mark.asyncio
    async def test_initialization(self):
        """اختبار تهيئة المنزل"""
        downloader = WebsiteDownloader()
        await downloader.initialize()
        
        assert downloader.playwright is not None
        assert downloader.browser is not None
        assert downloader.session is not None
        assert len(downloader._contexts_pool) == downloader._max_contexts
        
        await downloader.close()
    
    @pytest.mark.asyncio
    async def test_memory_check(self, downloader):
        """اختبار فحص الذاكرة"""
        # محاكاة استهلاك ذاكرة عالي
        with patch('psutil.Process') as mock_process:
            mock_memory = Mock()
            mock_memory.rss = 1024 * 1024 * 1024  # 1GB
            mock_process.return_value.memory_info.return_value = mock_memory
            
            result = await downloader._check_memory_usage()
            assert result is False  # يجب أن يعيد False للذاكرة العالية
    
    @pytest.mark.asyncio
    async def test_progress_callback(self, downloader):
        """اختبار دالة التقدم"""
        progress_calls = []
        
        async def mock_callback(progress, message):
            progress_calls.append((progress, message))
        
        downloader.set_progress_callback(mock_callback)
        await downloader._update_progress(50.0, "اختبار")
        
        assert len(progress_calls) == 1
        assert progress_calls[0] == (50.0, "اختبار")
    
    @pytest.mark.asyncio
    async def test_cancel_download(self, downloader):
        """اختبار إلغاء التنزيل"""
        downloader.cancel_download()
        assert downloader.cancel_event.is_set()
    
    @pytest.mark.asyncio
    async def test_compress_html(self, downloader):
        """اختبار ضغط HTML"""
        html = """
        <!-- تعليق -->
        <html>
            <head>
                <title>اختبار</title>
            </head>
            <body>
                <p>محتوى الصفحة</p>
            </body>
        </html>
        """
        
        compressed = await downloader._compress_html(html)
        
        # يجب أن يكون الحجم أصغر
        assert len(compressed) < len(html)
        # يجب ألا يحتوي على تعليقات
        assert "<!--" not in compressed
        # يجب أن يحتفظ بالمحتوى الأساسي
        assert "اختبار" in compressed
        assert "محتوى الصفحة" in compressed
    
    @pytest.mark.asyncio
    async def test_create_zip_archive(self, downloader, temp_dir):
        """اختبار إنشاء أرشيف ZIP"""
        # إنشاء ملفات اختبار
        test_file = os.path.join(temp_dir, "test.html")
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("<html><body>اختبار</body></html>")
        
        zip_path = await downloader._create_zip_archive(temp_dir)
        
        # التحقق من وجود ملف ZIP
        assert os.path.exists(zip_path)
        assert zip_path.endswith('.zip')
        
        # التنظيف
        if os.path.exists(zip_path):
            os.remove(zip_path)
    
    @pytest.mark.asyncio
    async def test_download_with_cache(self, downloader, temp_dir):
        """اختبار التنزيل مع الكاش"""
        url = "https://example.com"
        
        # محاكاة نتيجة مخزنة في الكاش
        cached_result = {
            'path': '/fake/path.zip',
            'files': 5,
            'size': 1024
        }
        
        with patch.object(cache_manager, 'get', return_value=cached_result):
            result = await downloader.download_website(url, temp_dir)
            
            assert result == (cached_result['path'], cached_result['files'], cached_result['size'])
    
    @pytest.mark.asyncio
    async def test_security_validation(self, downloader, temp_dir):
        """اختبار التحقق الأمني"""
        malicious_url = "javascript:alert('xss')"
        
        # محاكاة فحص أمني فاشل
        security_result = {
            'is_safe': False,
            'threats': ['نمط مشبوه: javascript:']
        }
        
        with patch.object(security_manager, 'validate_url_security', return_value=security_result):
            with pytest.raises(Exception) as exc_info:
                await downloader.download_website(malicious_url, temp_dir, user_id=123)
            
            assert "رابط غير آمن" in str(exc_info.value)

class TestCacheManager:
    """اختبارات مدير الكاش"""
    
    @pytest.mark.asyncio
    async def test_set_and_get(self):
        """اختبار حفظ واسترداد الكاش"""
        key = "test_key"
        value = {"data": "test_value"}
        
        await cache_manager.set(key, value, ttl=60)
        retrieved = await cache_manager.get(key)
        
        assert retrieved == value
    
    @pytest.mark.asyncio
    async def test_expiration(self):
        """اختبار انتهاء صلاحية الكاش"""
        key = "expire_test"
        value = {"data": "expire_value"}
        
        # حفظ مع مدة قصيرة جداً
        await cache_manager.set(key, value, ttl=0.1)
        
        # انتظار انتهاء الصلاحية
        await asyncio.sleep(0.2)
        
        retrieved = await cache_manager.get(key)
        assert retrieved is None
    
    @pytest.mark.asyncio
    async def test_cache_stats(self):
        """اختبار إحصائيات الكاش"""
        # إضافة بعض البيانات
        await cache_manager.set("stats_test_1", {"data": 1})
        await cache_manager.set("stats_test_2", {"data": 2})
        
        stats = cache_manager.get_stats()
        
        assert stats['total_items'] >= 2
        assert 'memory_usage' in stats
        assert 'hit_rate' in stats

class TestSecurityManager:
    """اختبارات مدير الأمان"""
    
    @pytest.mark.asyncio
    async def test_url_validation_safe(self):
        """اختبار التحقق من رابط آمن"""
        safe_url = "https://www.google.com"
        
        result = await security_manager.validate_url_security(safe_url)
        
        assert result['is_safe'] is True
        assert len(result['threats']) == 0
        assert result['risk_level'] == 'low'
    
    @pytest.mark.asyncio
    async def test_url_validation_malicious(self):
        """اختبار التحقق من رابط ضار"""
        malicious_url = "javascript:alert('xss')"
        
        result = await security_manager.validate_url_security(malicious_url)
        
        assert result['is_safe'] is False
        assert len(result['threats']) > 0
        assert result['risk_level'] in ['medium', 'high']
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """اختبار حدود المعدل"""
        user_id = 12345
        
        # أول طلب يجب أن يمر
        result1 = await security_manager.check_rate_limit(user_id, 'test')
        assert result1['allowed'] is True
        
        # محاكاة تجاوز الحد
        for _ in range(100):  # تجاوز الحد الافتراضي
            await security_manager.check_rate_limit(user_id, 'test')
        
        # الطلب التالي يجب أن يُرفض
        result2 = await security_manager.check_rate_limit(user_id, 'test')
        assert result2['allowed'] is False
    
    @pytest.mark.asyncio
    async def test_input_validation(self):
        """اختبار التحقق من المدخلات"""
        # مدخل آمن
        safe_input = "نص عادي آمن"
        result1 = await security_manager.validate_user_input(safe_input)
        assert result1['is_safe'] is True
        
        # مدخل ضار
        malicious_input = "<script>alert('xss')</script>"
        result2 = await security_manager.validate_user_input(malicious_input)
        assert result2['is_safe'] is False
        assert len(result2['threats']) > 0
    
    @pytest.mark.asyncio
    async def test_token_generation_and_verification(self):
        """اختبار إنشاء والتحقق من الرموز"""
        user_id = 123
        permissions = ['download', 'admin']
        
        # إنشاء رمز
        token = await security_manager.generate_secure_token(user_id, permissions)
        assert isinstance(token, str)
        assert len(token) > 0
        
        # التحقق من الرمز
        verification = await security_manager.verify_token(token)
        assert verification['valid'] is True
        assert verification['user_id'] == user_id
        assert verification['permissions'] == permissions

class TestQueueManager:
    """اختبارات مدير القوائل"""
    
    @pytest.fixture
    async def queue_manager(self):
        """إنشاء مدير قوائل للاختبار"""
        from services.queue_manager import DownloadQueue
        queue = DownloadQueue(max_concurrent=2)
        await queue.start()
        yield queue
        await queue.stop()
    
    @pytest.mark.asyncio
    async def test_add_task(self, queue_manager):
        """اختبار إضافة مهمة"""
        user_id = 123
        url = "https://example.com"
        
        task_id = await queue_manager.add_task(user_id, url)
        
        assert isinstance(task_id, str)
        assert len(task_id) > 0
        
        # التحقق من حالة المهمة
        task = await queue_manager.get_task_status(task_id)
        assert task is not None
        assert task.user_id == user_id
        assert task.url == url
    
    @pytest.mark.asyncio
    async def test_cancel_task(self, queue_manager):
        """اختبار إلغاء مهمة"""
        user_id = 123
        url = "https://example.com"
        
        task_id = await queue_manager.add_task(user_id, url)
        
        # إلغاء المهمة
        cancelled = await queue_manager.cancel_task(task_id, user_id)
        assert cancelled is True
        
        # التحقق من الحالة
        task = await queue_manager.get_task_status(task_id)
        assert task.status.value == 'cancelled'
    
    @pytest.mark.asyncio
    async def test_user_queue_limit(self, queue_manager):
        """اختبار حد قائمة المستخدم"""
        user_id = 123
        
        # إضافة مهام حتى الحد الأقصى
        task_ids = []
        for i in range(5):  # الحد الافتراضي
            task_id = await queue_manager.add_task(user_id, f"https://example{i}.com")
            task_ids.append(task_id)
        
        # محاولة إضافة مهمة إضافية يجب أن تفشل
        with pytest.raises(Exception) as exc_info:
            await queue_manager.add_task(user_id, "https://overflow.com")
        
        assert "تجاوز الحد الأقصى" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_queue_stats(self, queue_manager):
        """اختبار إحصائيات القائمة"""
        stats = queue_manager.get_queue_stats()
        
        assert 'pending_tasks' in stats
        assert 'running_tasks' in stats
        assert 'completed_tasks' in stats
        assert 'max_concurrent' in stats

# تشغيل الاختبارات
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
