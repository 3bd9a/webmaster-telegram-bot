import asyncio
import aiohttp
import aiofiles
import os
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from pathlib import Path
import magic
from datetime import datetime

# استيرادات مطلقة بدلاً من نسبية
from utils.logger import logger
from utils.helpers import sanitize_filename

class WebsiteDownloader:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.session = None
        self.downloaded_files = set()
        self.total_size = 0
        self.total_files = 0
        
    async def initialize(self):
        """تهيئة المتصفح وجلسة HTTP"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch()
        self.context = await self.browser.new_context()
        self.session = aiohttp.ClientSession()
        
    async def close(self):
        """إغلاق الموارد"""
        if self.session:
            await self.session.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    # ... باقي الدوال بدون تغيير ...
    
    async def download_website(self, url, output_dir, max_depth=2, max_size=50*1024*1024):
        """تنزيل الموقع بالكامل"""
        try:
            parsed_url = urlparse(url)
            base_domain = parsed_url.netloc
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            
            # إنشاء مجلد التنزيل
            domain_dir = os.path.join(output_dir, sanitize_filename(base_domain))
            os.makedirs(domain_dir, exist_ok=True)
            
            # تنزيل الصفحة الرئيسية أولاً
            main_page_path = await self.download_page(url, domain_dir, base_url)
            
            if main_page_path:
                # استخراج الروابط من الصفحة الرئيسية
                links = await self.extract_links(url, domain_dir, base_url)
                
                # تنزيل الروابط الداخلية
                for link in links[:10]:  # حد 10 صفحات للبداية
                    if self.total_size < max_size:
                        await self.download_page(link, domain_dir, base_url)
            
            return domain_dir, self.total_files, self.total_size
            
        except Exception as e:
            logger.error(f"Error downloading website: {e}")
            raise
    
    async def download_page(self, url, output_dir, base_url):
        """تنزيل صفحة فردية"""
        try:
            if url in self.downloaded_files:
                return None
                
            self.downloaded_files.add(url)
            
            # استخدام Playwright للحصول على المحتوى المعالج بالجافاسكريبت
            page = await self.context.new_page()
            await page.goto(url, wait_until='networkidle')
            
            # الحصول على HTML بعد معالجة الجافاسكريبت
            content = await page.content()
            
            # حفظ HTML
            parsed_url = urlparse(url)
            filename = sanitize_filename(parsed_url.path or "index") + ".html"
            if filename == ".html":
                filename = "index.html"
                
            filepath = os.path.join(output_dir, filename)
            
            async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
                await f.write(content)
            
            # تحديث الإحصائيات
            file_size = os.path.getsize(filepath)
            self.total_size += file_size
            self.total_files += 1
            
            # استخراج وتنزيل الموارد (CSS, JS, Images)
            await self.download_resources(content, output_dir, base_url)
            
            await page.close()
            return filepath
            
        except Exception as e:
            logger.error(f"Error downloading page {url}: {e}")
            return None
    
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
