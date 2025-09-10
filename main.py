#!/usr/bin/env python3
"""
بوت تيليجرام لتنزيل المواقع الكاملة
WebMaster Bot - أفضل بوت لتنزيل المواقع مع دعم JavaScript الكامل
"""

import asyncio
import logging
import os
import sys
import signal
from pathlib import Path

# إضافة مسار المشروع إلى sys.path
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from bot.handlers import BotHandlers
from utils.logger import setup_logger
import config

# إعداد نظام التسجيل المحسن
logger = setup_logger("webmaster_bot", getattr(logging, config.Config.LOG_LEVEL, logging.INFO))

async def shutdown_handler(application, bot_handlers):
    """معالج إيقاف البوت بشكل آمن"""
    logger.info("🔄 جاري إيقاف البوت بشكل آمن...")
    
    try:
        if application:
            await application.stop()
            logger.info("✅ تم إيقاف التطبيق")
        
        if bot_handlers and hasattr(bot_handlers, 'downloader'):
            await bot_handlers.downloader.close()
            logger.info("✅ تم إغلاق محرك التنزيل")
            
        if bot_handlers:
            await bot_handlers.cleanup()
            logger.info("✅ تم تنظيف الموارد")
            
    except Exception as e:
        logger.error(f"❌ خطأ أثناء الإيقاف: {e}")
    
    logger.info("🛑 تم إيقاف البوت بنجاح")

async def main():
    """الدالة الرئيسية لتشغيل البوت"""
    application = None
    bot_handlers = None
    
    try:
        logger.info("🚀 بدء تشغيل WebMaster Bot...")
        
        # التحقق من الإعدادات
        config.Config.validate()
        logger.info("✅ تم التحقق من الإعدادات بنجاح")
        
        # تهيئة البوت
        application = Application.builder().token(config.Config.BOT_TOKEN).build()
        logger.info("✅ تم تهيئة التطبيق")
        
        # تهيئة المعالجات
        bot_handlers = BotHandlers()
        await bot_handlers.initialize()
        logger.info("✅ تم تهيئة معالجات البوت")
        
        # تسجيل المعالجات
        handlers = [
            CommandHandler("start", bot_handlers.start),
            CommandHandler("admin", bot_handlers.admin_panel),
            CommandHandler("stats", bot_handlers.stats),
            CommandHandler("history", bot_handlers.history),
            CommandHandler("settings", bot_handlers.settings),
            CommandHandler("help", bot_handlers.help_command),
            CommandHandler("cancel", bot_handlers.cancel),
            CommandHandler("broadcast", bot_handlers.broadcast),
            CommandHandler("ban", bot_handlers.ban_command),
            CommandHandler("unban", bot_handlers.unban_command),
            CommandHandler("cleanup", bot_handlers.cleanup_command),
            CommandHandler("sysinfo", bot_handlers.system_info),
            MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handlers.handle_message),
            CallbackQueryHandler(bot_handlers.handle_callback)
        ]
        
        for handler in handlers:
            application.add_handler(handler)
        
        logger.info("✅ تم تسجيل جميع المعالجات")
        
        # إعداد معالج الإيقاف
        def signal_handler(signum, frame):
            logger.info(f"📡 تم استلام إشارة الإيقاف: {signum}")
            asyncio.create_task(shutdown_handler(application, bot_handlers))
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # بدء البوت
        await application.initialize()
        await application.start()
        await application.updater.start_polling(
            allowed_updates=["message", "callback_query", "inline_query"]
        )
        
        logger.info("🎉 البوت يعمل الآن! اضغط Ctrl+C للإيقاف")
        logger.info(f"📊 معرف المشرف: {config.Config.ADMIN_ID}")
        
        # البقاء في حالة تشغيل مع تنظيف دوري
        cleanup_counter = 0
        while True:
            await asyncio.sleep(60)  # فحص كل دقيقة
            cleanup_counter += 1
            
            # تنظيف دوري كل ساعة
            if cleanup_counter >= 60:
                if bot_handlers:
                    await bot_handlers.periodic_cleanup()
                cleanup_counter = 0
            
    except KeyboardInterrupt:
        logger.info("⏹️ تم طلب إيقاف البوت من المستخدم")
    except Exception as e:
        logger.error(f"❌ خطأ في تشغيل البوت: {e}")
        raise
    finally:
        await shutdown_handler(application, bot_handlers)

if __name__ == "__main__":
    try:
        # تشغيل البوت
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 وداعاً!")
    except Exception as e:
        logger.critical(f"💥 خطأ حرج في البوت: {e}")
        sys.exit(1)
