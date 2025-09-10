import asyncio
import aiohttp
import aiofiles
import os
import hashlib
import json
import zipfile
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from pathlib import Path
import magic
from datetime import datetime, timedelta
import psutil
import gc
import weakref
from typing import Dict, Optional, Callable, Any

# استيرادات مطلقة بدلاً من نسبية
from utils.logger import logger
from utils.helpers import sanitize_filename, human_readable_size
from services.cache_manager import cache_manager
from services.security_manager import security_manager
import config

class WebsiteDownloader:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.session = None
        self.downloaded_files = set()
        self.total_size = 0
        self.total_files = 0
        self.progress_callback = None
        self.cancel_event = asyncio.Event()
        self.memory_limit = config.Config.MAX_MEMORY_USAGE
        self._contexts_pool = []
        self._max_contexts = 3
        self._current_context_index = 0
        
    async def initialize(self):
        """تهيئة المتصفح وجلسة HTTP مع إدارة محسنة للذاكرة"""
        try:
            self.playwright = await async_playwright().start()
            
            # إعدادات المتصفح المحسنة لتقليل استهلاك الذاكرة
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=[
                    '--disable-gpu',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--no-zygote',
                    '--single-process',
                    '--disable-extensions',
                    '--disable-software-rasterizer',
                    '--disable-notifications',
                    '--mute-audio',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-breakpad',
                    '--disable-client-side-phishing-detection',
                    '--disable-component-extensions-with-background-pages',
                    '--disable-default-apps',
                    '--disable-hang-monitor',
                    '--disable-ipc-flooding-protection',
                    '--disable-popup-blocking',
                    '--disable-prompt-on-repost',
                    '--disable-renderer-backgrounding',
                    '--disable-sync',
                    '--metrics-recording-only',
                    '--no-default-browser-check',
                    '--use-fake-ui-for-media-stream',
                    '--window-size=1280,720',
                    '--memory-pressure-off',
                    '--max_old_space_size=512',
                    '--disable-background-networking',
                    '--disable-default-apps',
                    '--disable-translate'
                ]
            )
            
            # إنشاء مجموعة من السياقات لإعادة الاستخدام
            await self._create_contexts_pool()
            
            # إنشاء جلسة HTTP مع إعدادات محسنة
            connector = aiohttp.TCPConnector(
                limit=100,
                limit_per_host=10,
                ttl_dns_cache=300,
                use_dns_cache=True,
                keepalive_timeout=30,
                enable_cleanup_closed=True
            )
            
            timeout = aiohttp.ClientTimeout(total=300, connect=30)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            )
            
            logger.info("✅ تم تهيئة المتصفح وجلسة HTTP بنجاح")
            
        except Exception as e:
            logger.error(f"❌ خطأ في تهيئة المتصفح: {e}")
            await self.close()
            raise
        
    async def close(self):
        """إغلاق الموارد مع تنظيف شامل للذاكرة"""
        try:
            # إغلاق جلسة HTTP
            if self.session and not self.session.closed:
                await self.session.close()
                await asyncio.sleep(0.1)  # انتظار قصير للتنظيف
            
            # إغلاق مجموعة السياقات
            for context in self._contexts_pool:
                try:
                    await context.close()
                except Exception as e:
                    logger.warning(f"⚠️ خطأ في إغلاق السياق: {e}")
            
            self._contexts_pool.clear()
            
            # إغلاق السياق الرئيسي
            if self.context:
                try:
                    await self.context.close()
                except Exception as e:
                    logger.warning(f"⚠️ خطأ في إغلاق السياق الرئيسي: {e}")
            
            # إغلاق المتصفح
            if self.browser:
                try:
                    await self.browser.close()
                except Exception as e:
                    logger.warning(f"⚠️ خطأ في إغلاق المتصفح: {e}")
            
            # إيقاف Playwright
            if self.playwright:
                try:
                    await self.playwright.stop()
                except Exception as e:
                    logger.warning(f"⚠️ خطأ في إيقاف Playwright: {e}")
            
            # تنظيف المتغيرات
            self.session = None
            self.context = None
            self.browser = None
            self.playwright = None
            
            # تشغيل جامع القمامة
            gc.collect()
            
            logger.info("✅ تم إغلاق جميع الموارد بنجاح")
            
        except Exception as e:
            logger.error(f"❌ خطأ في إغلاق الموارد: {e}")
    
    async def _create_contexts_pool(self):
        """إنشاء مجموعة من السياقات لإعادة الاستخدام"""
        for i in range(self._max_contexts):
            context = await self.browser.new_context(
                viewport={'width': 1280, 'height': 720},
                device_scale_factor=1,
                is_mobile=False,
                has_touch=False,
                java_script_enabled=True,
                locale='en-US',
                timezone_id='UTC',
                ignore_https_errors=True,
                bypass_csp=True
            )
            
            # تعطيل طلبات الموارد غير الضرورية
            await context.route('**/*.{png,jpg,jpeg,gif,svg,woff,woff2,ttf,eot,ico}', 
                              lambda route: route.abort())
            
            self._contexts_pool.append(context)
    
    async def _get_context(self):
        """الحصول على سياق من المجموعة"""
        context = self._contexts_pool[self._current_context_index]
        self._current_context_index = (self._current_context_index + 1) % self._max_contexts
        return context
    
    async def _check_memory_usage(self):
        """فحص استهلاك الذاكرة"""
        process = psutil.Process()
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / 1024 / 1024
        
        if memory_mb > self.memory_limit:
            logger.warning(f"⚠️ استهلاك ذاكرة عالي: {memory_mb:.1f}MB")
            # تشغيل جامع القمامة
            gc.collect()
            return False
        return True
    
    def set_progress_callback(self, callback: Callable[[float, str], None]):
        """تعيين دالة تحديث التقدم"""
        self.progress_callback = callback
    
    def cancel_download(self):
        """إلغاء التنزيل"""
        self.cancel_event.set()
    
    async def _update_progress(self, progress: float, message: str = ""):
        """تحديث التقدم"""
        if self.progress_callback:
            try:
                await self.progress_callback(progress, message)
            except Exception as e:
                logger.error(f"خطأ في تحديث التقدم: {e}")
    
    async def download_website(self, url, output_dir, max_depth=2, max_size=50*1024*1024, user_id=None):
        """تنزيل الموقع بالكامل مع دعم الكاش والأمان"""
        try:
            # فحص الأمان
            if user_id:
                security_check = await security_manager.validate_url_security(url, user_id)
                if not security_check['is_safe']:
                    raise Exception(f"رابط غير آمن: {', '.join(security_check['threats'])}")
            
            # فحص الكاش
            cache_key = f"website_{hashlib.md5(url.encode()).hexdigest()}"
            cached_result = await cache_manager.get(cache_key)
            
            if cached_result:
                logger.info(f"📦 تم العثور على نسخة مخزنة للموقع: {url}")
                await self._update_progress(100.0, "تم استرداد الموقع من الكاش")
                return cached_result['path'], cached_result['files'], cached_result['size']
            
            await self._update_progress(5.0, "بدء تحليل الموقع...")
            
            parsed_url = urlparse(url)
            base_domain = parsed_url.netloc
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            
            # إنشاء مجلد التنزيل
            domain_dir = os.path.join(output_dir, sanitize_filename(base_domain))
            os.makedirs(domain_dir, exist_ok=True)
            
            await self._update_progress(10.0, "تنزيل الصفحة الرئيسية...")
            
            # تنزيل الصفحة الرئيسية أولاً
            main_page_path = await self.download_page(url, domain_dir, base_url)
            
            if main_page_path:
                await self._update_progress(30.0, "استخراج الروابط...")
                
                # استخراج الروابط من الصفحة الرئيسية
                links = await self.extract_links(url, domain_dir, base_url)
                
                # تنزيل الروابط الداخلية
                total_links = min(len(links), 10)  # حد 10 صفحات للبداية
                
                for i, link in enumerate(links[:total_links]):
                    if self.cancel_event.is_set():
                        logger.info("🚫 تم إلغاء التنزيل")
                        break
                    
                    if self.total_size < max_size:
                        progress = 30 + (i / total_links) * 60
                        await self._update_progress(progress, f"تنزيل الصفحة {i+1}/{total_links}...")
                        await self.download_page(link, domain_dir, base_url)
                        
                        # فحص استهلاك الذاكرة
                        if not await self._check_memory_usage():
                            logger.warning("⚠️ تم إيقاف التنزيل بسبب استهلاك الذاكرة")
                            break
            
            await self._update_progress(90.0, "إنشاء الأرشيف...")
            
            # إنشاء ملف ZIP
            zip_path = await self._create_zip_archive(domain_dir)
            
            # حفظ في الكاش
            cache_data = {
                'path': zip_path,
                'files': self.total_files,
                'size': self.total_size,
                'created_at': datetime.utcnow().isoformat()
            }
            await cache_manager.set(cache_key, cache_data, ttl=3600)  # كاش لساعة واحدة
            
            await self._update_progress(100.0, "تم إكمال التنزيل بنجاح")
            
            return zip_path, self.total_files, self.total_size
            
        except Exception as e:
            logger.error(f"❌ خطأ في تنزيل الموقع: {e}")
            await self._update_progress(0.0, f"خطأ: {str(e)}")
            raise
    
    async def download_page(self, url, output_dir, base_url):
        """تنزيل صفحة فردية مع إدارة محسنة للذاكرة"""
        try:
            if url in self.downloaded_files or self.cancel_event.is_set():
                return None
                
            self.downloaded_files.add(url)
            
            # الحصول على سياق من المجموعة
            context = await self._get_context()
            page = await context.new_page()
            
            try:
                # تعيين مهلة أطول للصفحات الثقيلة
                await page.goto(url, timeout=60000, wait_until='domcontentloaded')
                
                # انتظار تحميل الصفحة مع مهلة قصيرة
                try:
                    await page.wait_for_load_state('networkidle', timeout=15000)
                except Exception:
                    # المتابعة حتى لو لم تكتمل الشبكة
                    pass
                
                # تحسين الصفحة وتقليل حجمها
                await page.evaluate("""() => {
                    // حذف العناصر غير الضرورية
                    const selectors = [
                        'script[src*="analytics"]', 'script[src*="gtag"]', 'script[src*="facebook"]',
                        'iframe[src*="youtube"]', 'iframe[src*="twitter"]', 'iframe[src*="instagram"]',
                        '.advertisement', '.ads', '.social-share', '.popup', '.modal',
                        'header', 'footer', 'nav', '[role="banner"]', '[role="navigation"]'
                    ];
                    
                    selectors.forEach(selector => {
                        document.querySelectorAll(selector).forEach(el => el.remove());
                    });
                    
                    // تحسين الصور
                    document.querySelectorAll('img').forEach(img => {
                        img.loading = 'lazy';
                        if (img.width > 600) {
                            img.width = 600;
                            img.height = 'auto';
                        }
                        // إزالة الصور الكبيرة جداً
                        if (img.naturalWidth > 2000 || img.naturalHeight > 2000) {
                            img.remove();
                        }
                    });
                    
                    // تنظيف CSS غير المستخدم
                    document.querySelectorAll('style').forEach(style => {
                        if (style.textContent.length > 50000) {
                            style.remove();
                        }
                    });
                }""")
                
            except Exception as e:
                logger.warning(f"⚠️ تحذير أثناء معالجة الصفحة: {e}")
            
            # الحصول على HTML بعد المعالجة
            content = await page.content()
            
            # حفظ HTML
            parsed_url = urlparse(url)
            filename = sanitize_filename(parsed_url.path or "index") + ".html"
            if filename == ".html":
                filename = "index.html"
                
            filepath = os.path.join(output_dir, filename)
            
            # ضغط المحتوى إذا كان كبيراً
            if len(content) > 1024 * 1024:  # 1MB
                content = await self._compress_html(content)
            
            async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
                await f.write(content)
            
            # تحديث الإحصائيات
            file_size = os.path.getsize(filepath)
            self.total_size += file_size
            self.total_files += 1
            
            # استخراج وتنزيل الموارد المهمة فقط
            await self.download_resources(content, output_dir, base_url)
            
            await page.close()
            
            # فحص الذاكرة بعد كل صفحة
            await self._check_memory_usage()
            
            return filepath
            
        except Exception as e:
            logger.error(f"❌ خطأ في تنزيل الصفحة {url}: {e}")
            return None
    
    async def _compress_html(self, html_content: str) -> str:
        """ضغط محتوى HTML"""
        try:
            # إزالة المسافات الزائدة والتعليقات
            import re
            
            # إزالة التعليقات
            html_content = re.sub(r'<!--.*?-->', '', html_content, flags=re.DOTALL)
            
            # إزالة المسافات الزائدة
            html_content = re.sub(r'\s+', ' ', html_content)
            
            # إزالة المسافات حول العلامات
            html_content = re.sub(r'>\s+<', '><', html_content)
            
            return html_content.strip()
            
        except Exception as e:
            logger.warning(f"⚠️ خطأ في ضغط HTML: {e}")
            return html_content
    
    async def _create_zip_archive(self, directory_path: str) -> str:
        """إنشاء أرشيف ZIP للمجلد"""
        try:
            zip_path = f"{directory_path}.zip"
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
                for root, dirs, files in os.walk(directory_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arc_name = os.path.relpath(file_path, directory_path)
                        zipf.write(file_path, arc_name)
            
            # حذف المجلد الأصلي لتوفير المساحة
            import shutil
            shutil.rmtree(directory_path)
            
            return zip_path
            
        except Exception as e:
            logger.error(f"❌ خطأ في إنشاء الأرشيف: {e}")
            return directory_path
    
    async def download_resources(self, html_content, output_dir, base_url):
        """تنزيل الموارد المرتبطة بالصفحة"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # روابط CSS
        for link in soup.find_all('link', rel='stylesheet'):
            href = link.get('href')
            if href:
                await self.download_resource(href, output_dir, base_url, 'css')
        
        # سكريبتات JS
        for script in soup.find_all('script', src=True):
            src = script.get('src')
            if src:
                await self.download_resource(src, output_dir, base_url, 'js')
        
        # صور
        for img in soup.find_all('img', src=True):
            src = img.get('src')
            if src:
                await self.download_resource(src, output_dir, base_url, 'images')
    
    async def download_resource(self, resource_url, output_dir, base_url, resource_type):
        """تنزيل مورد فردي"""
        try:
            if not resource_url.startswith(('http', '//')):
                resource_url = urljoin(base_url, resource_url)
            
            if resource_url in self.downloaded_files:
                return
                
            self.downloaded_files.add(resource_url)
            
            async with self.session.get(resource_url) as response:
                if response.status == 200:
                    content = await response.read()
                    
                    # إنشاء مجلد للمورد
                    resource_dir = os.path.join(output_dir, resource_type)
                    os.makedirs(resource_dir, exist_ok=True)
                    
                    # إنشاء اسم ملف فريد
                    filename = os.path.basename(urlparse(resource_url).path)
                    if not filename:
                        filename = f"resource_{hash(resource_url)}"
                    
                    filepath = os.path.join(resource_dir, filename)
                    
                    async with aiofiles.open(filepath, 'wb') as f:
                        await f.write(content)
                    
                    # تحديث الإحصائيات
                    file_size = len(content)
                    self.total_size += file_size
                    self.total_files += 1
                    
        except Exception as e:
            logger.error(f"Error downloading resource {resource_url}: {e}")
    
    async def extract_links(self, url, output_dir, base_url):
        """استخراج الروابط من الصفحة"""
        try:
            page = await self.context.new_page()
            await page.goto(url, wait_until='networkidle')
            
            # الحصول على جميع الروابط الداخلية
            links = await page.evaluate('''() => {
                return Array.from(document.querySelectorAll('a[href]'))
                    .map(a => a.href)
                    .filter(href => href.startsWith(window.location.origin))
                    .filter(href => !href.includes('#'))
            }''')
            
            await page.close()
            return list(set(links))  # إزالة التكرارات
            
        except Exception as e:
            logger.error(f"Error extracting links: {e}")
            return []
