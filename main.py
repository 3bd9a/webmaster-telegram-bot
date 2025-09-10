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
import telegram
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

# إضافة مسار المشروع إلى sys.path
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

# استيراد المكونات المحدثة
from bot.handlers import BotHandlers
from utils.logger import setup_logger
from health_server import start_health_server
from services.queue_manager import download_queue
from services.monitoring import metrics_collector
from services.database_manager import db_manager
from services.cache_manager import cache_manager
from services.security_manager import security_manager
import config

# إعداد نظام التسجيل المحسن
logger = setup_logger("webmaster_bot", getattr(logging, config.Config.LOG_LEVEL, logging.INFO))

async def shutdown_handler(application, bot_handlers):
    """معالج إيقاف البوت بشكل آمن مع تنظيف شامل"""
    logger.info("🔄 جاري إيقاف البوت بشكل آمن...")
    
    try:
        # إيقاف قوائل الانتظار
        await download_queue.stop()
        logger.info("✅ تم إيقاف قوائل الانتظار")
        
        # إيقاف نظام المراقبة
        await metrics_collector.stop()
        logger.info("✅ تم إيقاف نظام المراقبة")
        
        # إغلاق قاعدة البيانات
        await db_manager.close()
        logger.info("✅ تم إغلاق قاعدة البيانات")
        
        # تنظيف الكاش
        await cache_manager.cleanup()
        logger.info("✅ تم تنظيف الكاش")
        
        # إيقاف التطبيق
        if application:
            await application.stop()
            logger.info("✅ تم إيقاف التطبيق")
        
        # إغلاق محرك التنزيل
        if bot_handlers and hasattr(bot_handlers, 'downloader'):
            await bot_handlers.downloader.close()
            logger.info("✅ تم إغلاق محرك التنزيل")
            
        # تنظيف معالجات البوت
        if bot_handlers:
            await bot_handlers.cleanup()
            logger.info("✅ تم تنظيف معالجات البوت")
            
    except Exception as e:
        logger.error(f"❌ خطأ أثناء الإيقاف: {e}")
    
    logger.info("🛑 تم إيقاف البوت بنجاح")

async def main():
    """الدالة الرئيسية لتشغيل البوت"""
    application = None
    bot_handlers = None
    
    try:
        logger.info("🚀 بدء تشغيل WebMaster Bot المتطور...")
        
        # التحقق من الإعدادات
        config.Config.validate()
        logger.info("✅ تم التحقق من الإعدادات بنجاح")
        
        # تهيئة قاعدة البيانات
        await db_manager.initialize()
        logger.info("✅ تم تهيئة قاعدة البيانات")
        
        # بدء قوائل الانتظار
        await download_queue.start()
        logger.info("✅ تم بدء قوائل الانتظار")
        
        # بدء نظام المراقبة
        await metrics_collector.start()
        logger.info("✅ تم بدء نظام المراقبة")
        
        # بدء خادم الفحص الصحي
        health_thread = start_health_server()
        logger.info("✅ تم بدء خادم الفحص الصحي")
        
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
        
        # بدء البوت مع معالجة النسخ المتعددة
        await application.initialize()
        await application.start()
        
        # إعداد الـ polling مع معالجة الأخطاء
        await application.updater.start_polling(
            allowed_updates=["message", "callback_query", "inline_query"],
            drop_pending_updates=True,  # تجاهل الرسائل القديمة
            timeout=30  # مهلة انتظار أقصر
        )
        
        logger.info("🎉 البوت يعمل الآن! اضغط Ctrl+C للإيقاف")
        logger.info(f"📊 معرف المشرف: {config.Config.ADMIN_ID}")
        
        # البقاء في حالة تشغيل مع تنظيف دوري متقدم
        cleanup_counter = 0
        security_cleanup_counter = 0
        
        while True:
            await asyncio.sleep(60)  # فحص كل دقيقة
            cleanup_counter += 1
            security_cleanup_counter += 1
            
            # تنظيف دوري كل ساعة
            if cleanup_counter >= 60:
                if bot_handlers:
                    await bot_handlers.periodic_cleanup()
                
                # تنظيف الكاش المنتهي الصلاحية
                await cache_manager.cleanup_expired()
                
                # تنظيف قاعدة البيانات
                await db_manager.cleanup_expired_cache()
                
                cleanup_counter = 0
                logger.info("🧹 تم إجراء تنظيف دوري")
            
            # تنظيف بيانات الأمان كل 30 دقيقة
            if security_cleanup_counter >= 30:
                await security_manager.cleanup_old_data()
                security_cleanup_counter = 0
                
    except telegram.error.Conflict as e:
        logger.error(f"⚠️ خطأ: تم تشغيل البوت مسبقاً على جهاز آخر. {e}")
        logger.info("🔄 جاري إيقاف هذه النسخة...")
        if application:
            await application.stop()
            await application.shutdown()
        return
    except telegram.error.RetryAfter as e:
        logger.warning(f"⏳ تم تجاوز معدل الطلبات. جاري الانتظار لـ {e.retry_after} ثانية...")
        await asyncio.sleep(e.retry_after)
        # تسجيل حدث أمني
        await db_manager.log_event('WARNING', f'Rate limit exceeded: {e.retry_after}s', 'main')
    except telegram.error.TimedOut as e:
        logger.warning(f"⏱️ انتهت مهلة الطلب: {e}. جاري إعادة المحاولة...")
        await asyncio.sleep(5)
        await db_manager.log_event('WARNING', f'Request timeout: {e}', 'main')
    except telegram.error.NetworkError as e:
        logger.error(f"🌐 خطأ في الشبكة: {e}. جاري إعادة المحاولة...")
        await asyncio.sleep(5)
        await db_manager.log_event('ERROR', f'Network error: {e}', 'main')
    except KeyboardInterrupt:
        logger.info("⏹️ تم طلب إيقاف البوت من المستخدم")
        await db_manager.log_event('INFO', 'Bot stopped by user', 'main')
    except Exception as e:
        logger.error(f"❌ خطأ غير متوقع: {e}")
        await db_manager.log_event('CRITICAL', f'Unexpected error: {e}', 'main')
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
