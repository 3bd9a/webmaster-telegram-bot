"""
نظام الأمان والحماية المتقدم
Advanced Security and Protection System
"""

import asyncio
import hashlib
import hmac
import jwt
import time
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse
import requests
from dataclasses import dataclass
import ipaddress

from utils.logger import logger
import config

@dataclass
class SecurityThreat:
    """تهديد أمني"""
    user_id: int
    threat_type: str
    severity: str  # low, medium, high, critical
    description: str
    timestamp: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

class SecurityManager:
    """مدير الأمان المتقدم"""
    
    def __init__(self):
        self.blocked_ips = set()
        self.blocked_domains = set()
        self.suspicious_patterns = []
        self.threat_history = []
        self.rate_limits = {}
        self.failed_attempts = {}
        
        # تحميل قوائم الحماية
        self._load_security_lists()
        
        # إعدادات الأمان
        self.max_failed_attempts = 5
        self.lockout_duration = 3600  # ساعة واحدة
        self.jwt_secret = self._generate_jwt_secret()
    
    def _generate_jwt_secret(self) -> str:
        """إنشاء مفتاح JWT آمن"""
        return hashlib.sha256(f"{config.Config.BOT_TOKEN}security_salt".encode()).hexdigest()
    
    def _load_security_lists(self):
        """تحميل قوائم الحماية"""
        # نطاقات محظورة افتراضية
        self.blocked_domains.update([
            'localhost', '127.0.0.1', '0.0.0.0',
            '10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16',
            'malware.com', 'phishing.net', 'spam.org'
        ])
        
        # أنماط مشبوهة
        self.suspicious_patterns = [
            r'<script[^>]*>.*?</script>',  # JavaScript injection
            r'javascript:',  # JavaScript URLs
            r'data:text/html',  # Data URLs
            r'vbscript:',  # VBScript
            r'onload\s*=',  # Event handlers
            r'onerror\s*=',
            r'onclick\s*=',
            r'\.exe$', r'\.bat$', r'\.cmd$', r'\.scr$'  # Executable files
        ]
    
    async def validate_url_security(self, url: str, user_id: int = None) -> Dict[str, any]:
        """فحص أمان شامل للرابط"""
        result = {
            'is_safe': True,
            'threats': [],
            'risk_level': 'low',
            'recommendations': []
        }
        
        try:
            parsed_url = urlparse(url)
            
            # فحص البروتوكول
            if parsed_url.scheme not in ['http', 'https']:
                result['threats'].append('بروتوكول غير آمن')
                result['is_safe'] = False
                result['risk_level'] = 'high'
            
            # فحص النطاق
            domain_check = await self._check_domain_security(parsed_url.netloc)
            if not domain_check['is_safe']:
                result['threats'].extend(domain_check['threats'])
                result['is_safe'] = False
                result['risk_level'] = max(result['risk_level'], domain_check['risk_level'])
            
            # فحص الأنماط المشبوهة
            pattern_check = self._check_suspicious_patterns(url)
            if not pattern_check['is_safe']:
                result['threats'].extend(pattern_check['threats'])
                result['is_safe'] = False
                result['risk_level'] = max(result['risk_level'], pattern_check['risk_level'])
            
            # فحص قوائم الحماية الخارجية
            if config.Config.ENABLE_EXTERNAL_SECURITY_CHECK:
                external_check = await self._check_external_blacklists(url)
                if not external_check['is_safe']:
                    result['threats'].extend(external_check['threats'])
                    result['is_safe'] = False
                    result['risk_level'] = 'critical'
            
            # تسجيل التهديد إذا وُجد
            if not result['is_safe'] and user_id:
                await self._log_security_threat(
                    user_id=user_id,
                    threat_type='malicious_url',
                    severity=result['risk_level'],
                    description=f"رابط مشبوه: {url} - {', '.join(result['threats'])}"
                )
            
        except Exception as e:
            logger.error(f"❌ خطأ في فحص أمان الرابط: {e}")
            result['is_safe'] = False
            result['threats'].append('خطأ في فحص الأمان')
            result['risk_level'] = 'medium'
        
        return result
    
    async def _check_domain_security(self, domain: str) -> Dict[str, any]:
        """فحص أمان النطاق"""
        result = {'is_safe': True, 'threats': [], 'risk_level': 'low'}
        
        # فحص النطاقات المحظورة
        for blocked_domain in self.blocked_domains:
            if blocked_domain in domain.lower():
                result['threats'].append(f'نطاق محظور: {blocked_domain}')
                result['is_safe'] = False
                result['risk_level'] = 'high'
        
        # فحص عناوين IP المحلية
        try:
            ip = ipaddress.ip_address(domain)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                result['threats'].append('عنوان IP محلي')
                result['is_safe'] = False
                result['risk_level'] = 'high'
        except ValueError:
            pass  # ليس عنوان IP
        
        # فحص النطاقات المشبوهة
        suspicious_tlds = ['.tk', '.ml', '.ga', '.cf']
        for tld in suspicious_tlds:
            if domain.endswith(tld):
                result['threats'].append(f'امتداد نطاق مشبوه: {tld}')
                result['risk_level'] = 'medium'
        
        return result
    
    def _check_suspicious_patterns(self, url: str) -> Dict[str, any]:
        """فحص الأنماط المشبوهة"""
        result = {'is_safe': True, 'threats': [], 'risk_level': 'low'}
        
        for pattern in self.suspicious_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                result['threats'].append(f'نمط مشبوه: {pattern}')
                result['is_safe'] = False
                result['risk_level'] = 'high'
        
        return result
    
    async def _check_external_blacklists(self, url: str) -> Dict[str, any]:
        """فحص قوائم الحماية الخارجية"""
        result = {'is_safe': True, 'threats': [], 'risk_level': 'low'}
        
        try:
            # فحص Google Safe Browsing (مثال)
            # في التطبيق الحقيقي، استخدم API مناسب
            domain = urlparse(url).netloc
            
            # محاكاة فحص خارجي
            await asyncio.sleep(0.1)  # محاكاة زمن الاستجابة
            
            # هنا يمكن إضافة فحص حقيقي مع APIs خارجية
            
        except Exception as e:
            logger.error(f"❌ خطأ في الفحص الخارجي: {e}")
        
        return result
    
    async def check_rate_limit(self, user_id: int, action: str = 'general') -> Dict[str, any]:
        """فحص حدود المعدل المتقدم"""
        current_time = time.time()
        key = f"{user_id}:{action}"
        
        if key not in self.rate_limits:
            self.rate_limits[key] = []
        
        # تنظيف الطلبات القديمة
        self.rate_limits[key] = [
            timestamp for timestamp in self.rate_limits[key]
            if current_time - timestamp < 3600  # آخر ساعة
        ]
        
        # فحص الحدود
        limits = {
            'general': 100,  # 100 طلب في الساعة
            'download': 10,  # 10 تنزيلات في الساعة
            'admin': 1000   # 1000 طلب للمشرفين
        }
        
        limit = limits.get(action, 50)
        current_count = len(self.rate_limits[key])
        
        if current_count >= limit:
            # تسجيل محاولة تجاوز الحد
            await self._log_security_threat(
                user_id=user_id,
                threat_type='rate_limit_exceeded',
                severity='medium',
                description=f"تجاوز حد المعدل للعمل: {action} ({current_count}/{limit})"
            )
            
            return {
                'allowed': False,
                'limit': limit,
                'current': current_count,
                'reset_time': current_time + 3600
            }
        
        # إضافة الطلب الحالي
        self.rate_limits[key].append(current_time)
        
        return {
            'allowed': True,
            'limit': limit,
            'current': current_count + 1,
            'remaining': limit - current_count - 1
        }
    
    async def validate_user_input(self, input_text: str, user_id: int = None) -> Dict[str, any]:
        """فحص أمان مدخلات المستخدم"""
        result = {
            'is_safe': True,
            'threats': [],
            'sanitized_input': input_text
        }
        
        # فحص الأنماط المشبوهة
        for pattern in self.suspicious_patterns:
            if re.search(pattern, input_text, re.IGNORECASE):
                result['threats'].append(f'نمط مشبوه في المدخل: {pattern}')
                result['is_safe'] = False
        
        # فحص طول المدخل
        if len(input_text) > 10000:  # 10KB
            result['threats'].append('مدخل طويل جداً')
            result['is_safe'] = False
        
        # تنظيف المدخل
        result['sanitized_input'] = self._sanitize_input(input_text)
        
        if not result['is_safe'] and user_id:
            await self._log_security_threat(
                user_id=user_id,
                threat_type='malicious_input',
                severity='medium',
                description=f"مدخل مشبوه: {input_text[:100]}..."
            )
        
        return result
    
    def _sanitize_input(self, input_text: str) -> str:
        """تنظيف مدخلات المستخدم"""
        # إزالة HTML tags
        sanitized = re.sub(r'<[^>]+>', '', input_text)
        
        # إزالة JavaScript
        sanitized = re.sub(r'javascript:', '', sanitized, flags=re.IGNORECASE)
        
        # إزالة أحرف التحكم
        sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', sanitized)
        
        return sanitized.strip()
    
    async def generate_secure_token(self, user_id: int, permissions: List[str] = None) -> str:
        """إنشاء رمز آمن للمستخدم"""
        payload = {
            'user_id': user_id,
            'permissions': permissions or [],
            'issued_at': time.time(),
            'expires_at': time.time() + 3600  # ساعة واحدة
        }
        
        token = jwt.encode(payload, self.jwt_secret, algorithm='HS256')
        return token
    
    async def verify_token(self, token: str) -> Dict[str, any]:
        """التحقق من صحة الرمز"""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=['HS256'])
            
            # فحص انتهاء الصلاحية
            if payload['expires_at'] < time.time():
                return {'valid': False, 'reason': 'token_expired'}
            
            return {
                'valid': True,
                'user_id': payload['user_id'],
                'permissions': payload['permissions']
            }
            
        except jwt.InvalidTokenError as e:
            return {'valid': False, 'reason': str(e)}
    
    async def _log_security_threat(self, user_id: int, threat_type: str, 
                                 severity: str, description: str):
        """تسجيل تهديد أمني"""
        threat = SecurityThreat(
            user_id=user_id,
            threat_type=threat_type,
            severity=severity,
            description=description,
            timestamp=datetime.utcnow()
        )
        
        self.threat_history.append(threat)
        
        # تنظيف التاريخ القديم
        if len(self.threat_history) > 1000:
            self.threat_history = self.threat_history[-500:]
        
        # تسجيل في السجلات
        logger.warning(f"🚨 تهديد أمني: {threat_type} - {description} (المستخدم: {user_id})")
        
        # إجراءات تلقائية حسب الخطورة
        if severity == 'critical':
            await self._handle_critical_threat(user_id, threat)
        elif severity == 'high':
            await self._handle_high_threat(user_id, threat)
    
    async def _handle_critical_threat(self, user_id: int, threat: SecurityThreat):
        """معالجة التهديدات الحرجة"""
        # حظر فوري
        self.blocked_ips.add(str(user_id))  # في التطبيق الحقيقي، استخدم IP
        
        logger.critical(f"🚨 حظر فوري للمستخدم {user_id} بسبب تهديد حرج")
    
    async def _handle_high_threat(self, user_id: int, threat: SecurityThreat):
        """معالجة التهديدات عالية الخطورة"""
        # زيادة عداد المحاولات الفاشلة
        if user_id not in self.failed_attempts:
            self.failed_attempts[user_id] = {'count': 0, 'last_attempt': time.time()}
        
        self.failed_attempts[user_id]['count'] += 1
        self.failed_attempts[user_id]['last_attempt'] = time.time()
        
        # حظر مؤقت بعد عدة محاولات
        if self.failed_attempts[user_id]['count'] >= self.max_failed_attempts:
            logger.warning(f"⚠️ حظر مؤقت للمستخدم {user_id} لمدة {self.lockout_duration} ثانية")
    
    async def is_user_blocked(self, user_id: int) -> bool:
        """فحص إذا كان المستخدم محظور"""
        # فحص الحظر الدائم
        if str(user_id) in self.blocked_ips:
            return True
        
        # فحص الحظر المؤقت
        if user_id in self.failed_attempts:
            attempt_info = self.failed_attempts[user_id]
            if attempt_info['count'] >= self.max_failed_attempts:
                time_since_last = time.time() - attempt_info['last_attempt']
                if time_since_last < self.lockout_duration:
                    return True
                else:
                    # انتهت مدة الحظر
                    del self.failed_attempts[user_id]
        
        return False
    
    def get_security_stats(self) -> Dict:
        """الحصول على إحصائيات الأمان"""
        threat_counts = {}
        for threat in self.threat_history:
            threat_counts[threat.threat_type] = threat_counts.get(threat.threat_type, 0) + 1
        
        return {
            'total_threats': len(self.threat_history),
            'blocked_ips': len(self.blocked_ips),
            'blocked_domains': len(self.blocked_domains),
            'failed_attempts': len(self.failed_attempts),
            'threat_types': threat_counts,
            'recent_threats': [
                {
                    'user_id': t.user_id,
                    'type': t.threat_type,
                    'severity': t.severity,
                    'timestamp': t.timestamp.isoformat()
                }
                for t in self.threat_history[-10:]  # آخر 10 تهديدات
            ]
        }
    
    async def cleanup_old_data(self):
        """تنظيف البيانات القديمة"""
        current_time = time.time()
        
        # تنظيف حدود المعدل
        for key in list(self.rate_limits.keys()):
            self.rate_limits[key] = [
                timestamp for timestamp in self.rate_limits[key]
                if current_time - timestamp < 3600
            ]
            if not self.rate_limits[key]:
                del self.rate_limits[key]
        
        # تنظيف المحاولات الفاشلة
        for user_id in list(self.failed_attempts.keys()):
            attempt_info = self.failed_attempts[user_id]
            if current_time - attempt_info['last_attempt'] > self.lockout_duration * 2:
                del self.failed_attempts[user_id]
        
        # تنظيف تاريخ التهديدات
        week_ago = datetime.utcnow() - timedelta(days=7)
        self.threat_history = [
            threat for threat in self.threat_history
            if threat.timestamp > week_ago
        ]

# إنشاء مثيل عام للاستخدام
security_manager = SecurityManager()
