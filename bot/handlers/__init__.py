"""
معالجات البوت المحسنة
Bot Handlers Package - Enhanced Structure
"""

from .base_handler import BaseHandler
from .user_handlers import UserHandlers
from .admin_handlers import AdminHandlers
from .download_handlers import DownloadHandlers
from .callback_handlers import CallbackHandlers

# الفئة الرئيسية التي تجمع جميع المعالجات
class BotHandlers(BaseHandler):
    """معالج البوت الرئيسي المحسن"""
    
    def __init__(self):
        super().__init__()
        self.user_handlers = UserHandlers(self)
        self.admin_handlers = AdminHandlers(self)
        self.download_handlers = DownloadHandlers(self)
        self.callback_handlers = CallbackHandlers(self)
    
    async def initialize(self):
        """تهيئة جميع المعالجات"""
        await super().initialize()
        await self.user_handlers.initialize()
        await self.admin_handlers.initialize()
        await self.download_handlers.initialize()
        await self.callback_handlers.initialize()
    
    async def cleanup(self):
        """تنظيف جميع الموارد"""
        await self.user_handlers.cleanup()
        await self.admin_handlers.cleanup()
        await self.download_handlers.cleanup()
        await self.callback_handlers.cleanup()
        await super().cleanup()
    
    # تفويض المعالجات للفئات المناسبة
    async def start(self, update, context):
        return await self.user_handlers.start(update, context)
    
    async def handle_message(self, update, context):
        return await self.user_handlers.handle_message(update, context)
    
    async def handle_callback(self, update, context):
        return await self.callback_handlers.handle_callback(update, context)
    
    async def admin_panel(self, update, context):
        return await self.admin_handlers.admin_panel(update, context)
    
    async def stats(self, update, context):
        return await self.user_handlers.stats(update, context)
    
    async def history(self, update, context):
        return await self.user_handlers.history(update, context)
    
    async def settings(self, update, context):
        return await self.user_handlers.settings(update, context)
    
    async def help_command(self, update, context):
        return await self.user_handlers.help_command(update, context)
    
    async def cancel(self, update, context):
        return await self.download_handlers.cancel(update, context)
    
    async def broadcast(self, update, context):
        return await self.admin_handlers.broadcast(update, context)
    
    async def ban_command(self, update, context):
        return await self.admin_handlers.ban_command(update, context)
    
    async def unban_command(self, update, context):
        return await self.admin_handlers.unban_command(update, context)
    
    async def cleanup_command(self, update, context):
        return await self.admin_handlers.cleanup_command(update, context)
    
    async def system_info(self, update, context):
        return await self.admin_handlers.system_info(update, context)
