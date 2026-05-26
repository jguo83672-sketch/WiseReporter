"""
Cookie池管理模块
"""
import json
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from models import db, CookiePool
from config import Config

class CookieManager:
    """Cookie池管理器"""
    
    @staticmethod
    def get_cookies() -> Optional[Dict]:
        """获取一个可用的Cookie（兼容旧接口）"""
        return CookieManager.get_random_cookie()
    
    @staticmethod
    def parse_cookie_string(cookie_string: str) -> Dict:
        """
        解析Cookie字符串为JSON格式
        支持两种格式：
        1. key=value; key2=value2 格式
        2. {"key": "value", ...} JSON格式
        """
        cookie_string = cookie_string.strip()
        
        # 如果是JSON格式，直接解析
        if cookie_string.startswith('{'):
            try:
                return json.loads(cookie_string)
            except json.JSONDecodeError:
                raise ValueError("无效的JSON格式")
        
        # 解析 key=value; key2=value2 格式
        result = {}
        key_cookies = {}
        
        for item in cookie_string.split(';'):
            item = item.strip()
            if '=' in item:
                key, value = item.split('=', 1)
                key = key.strip()
                value = value.strip()
                result[key] = value
                
                # 提取关键Cookie
                if key in ['wxuin', 'bizuin', 'data_ticket', 'slave_user', 
                          'wxtokenkey', 'data_bizuin', 'slave_bizuin', 'ua_id',
                          'slave_sid', 'data_ticket', 'pac_uid', 'uuid']:
                    key_cookies[key] = value
        
        if not result:
            raise ValueError("Cookie字符串为空或格式不正确")
        
        return result
    
    @staticmethod
    def analyze_cookie(cookie_string: str) -> Dict:
        """
        分析Cookie字符串，返回详细信息
        """
        cookies = CookieManager.parse_cookie_string(cookie_string)
        
        # 关键Cookie分析
        analysis = {
            'is_valid': False,
            'wxuin': None,
            'bizuin': None,
            'has_data_ticket': False,
            'has_token': False,
            'total_count': len(cookies),
            'cookies': cookies,
            'message': ''
        }
        
        if 'wxuin' in cookies:
            analysis['wxuin'] = cookies['wxuin']
            analysis['is_valid'] = True
            
        if 'bizuin' in cookies:
            analysis['bizuin'] = cookies['bizuin']
            
        if 'data_ticket' in cookies:
            analysis['has_data_ticket'] = True
            
        if 'wxtokenkey' in cookies:
            analysis['has_token'] = True
            
        # 生成建议名称
        if analysis['wxuin']:
            analysis['suggested_name'] = f"微信账号_{analysis['wxuin'][-6:]}"
        elif analysis['bizuin']:
            analysis['suggested_name'] = f"公众号_{analysis['bizuin']}"
        else:
            analysis['suggested_name'] = f"Cookie_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # 验证状态
        if analysis['is_valid']:
            analysis['message'] = 'Cookie有效，包含微信身份信息'
        else:
            analysis['message'] = '警告：Cookie可能不完整'
            
        return analysis
    
    @staticmethod
    def get_random_cookie() -> Optional[Dict]:
        try:
            available_cookies = CookiePool.query.filter_by(
                is_available=True
            ).filter(
                db.or_(
                    CookiePool.expires_at.is_(None),
                    CookiePool.expires_at > datetime.utcnow()
                )
            ).all()
            
            if not available_cookies:
                print("[CookieManager] 没有可用的Cookie")
                return None
            
            # 随机选择一个Cookie
            cookie = random.choice(available_cookies)
            
            # 安全解析cookie_data
            cookie_data = cookie.cookie_data
            if isinstance(cookie_data, str):
                try:
                    cookies = json.loads(cookie_data)
                except json.JSONDecodeError as e:
                    print(f"[CookieManager] Cookie JSON解析失败: {e}, cookie_id={cookie.id}")
                    # 尝试修复常见的JSON格式问题
                    fixed = cookie_data.strip()
                    if fixed.startswith('{') and not fixed.endswith('}'):
                        fixed = fixed + '"}'
                    try:
                        cookies = json.loads(fixed)
                    except:
                        return None
            elif isinstance(cookie_data, dict):
                cookies = cookie_data
            else:
                print(f"[CookieManager] Cookie数据格式异常: {type(cookie_data)}")
                return None
            
            # 更新使用记录
            cookie.last_used = datetime.utcnow()
            db.session.commit()
            
            return {
                'cookies': cookies,
                'user_agent': cookie.user_agent or random.choice(Config.USER_AGENTS)
            }
        except Exception as e:
            print(f"[CookieManager] 获取Cookie失败: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            return None
    
    @staticmethod
    def get_least_used_cookie() -> Optional[Dict]:
        """获取使用次数最少的Cookie"""
        cookie = CookiePool.query.filter_by(
            is_available=True
        ).filter(
            db.or_(
                CookiePool.expires_at.is_(None),
                CookiePool.expires_at > datetime.utcnow()
            )
        ).order_by(CookiePool.last_used.asc().nullsfirst()).first()
        
        if not cookie:
            return None
        
        cookie.last_used = datetime.utcnow()
        db.session.commit()
        
        return {
            'cookies': json.loads(cookie.cookie_data),
            'user_agent': cookie.user_agent or random.choice(Config.USER_AGENTS)
        }
    
    @staticmethod
    def add_cookie(name: str, cookie_data: Dict, user_agent: str = None, 
                   expires_at: datetime = None) -> CookiePool:
        """添加Cookie到池中"""
        cookie = CookiePool(
            name=name,
            cookie_data=json.dumps(cookie_data),
            user_agent=user_agent,
            expires_at=expires_at,
            last_used=datetime.utcnow()
        )
        db.session.add(cookie)
        db.session.commit()
        return cookie
    
    @staticmethod
    def mark_cookie_failed(cookie_id: int) -> None:
        """标记Cookie失败"""
        cookie = CookiePool.query.get(cookie_id)
        if cookie:
            cookie.failure_count += 1
            if cookie.failure_count >= 5:
                cookie.is_available = False
            db.session.commit()
    
    @staticmethod
    def mark_cookie_success(cookie_id: int) -> None:
        """标记Cookie成功"""
        cookie = CookiePool.query.get(cookie_id)
        if cookie:
            cookie.failure_count = 0
            cookie.is_available = True
            db.session.commit()
    
    @staticmethod
    def delete_cookie(cookie_id: int) -> bool:
        """删除Cookie"""
        cookie = CookiePool.query.get(cookie_id)
        if cookie:
            db.session.delete(cookie)
            db.session.commit()
            return True
        return False
    
    @staticmethod
    def get_all_cookies() -> List[CookiePool]:
        """获取所有Cookie"""
        return CookiePool.query.all()
    
    @staticmethod
    def update_cookie(cookie_id: int, name: str = None, cookie_data: Dict = None,
                     user_agent: str = None, is_available: bool = None) -> Optional[CookiePool]:
        """更新Cookie"""
        cookie = CookiePool.query.get(cookie_id)
        if not cookie:
            return None
        
        if name:
            cookie.name = name
        if cookie_data:
            cookie.cookie_data = json.dumps(cookie_data)
        if user_agent:
            cookie.user_agent = user_agent
        if is_available is not None:
            cookie.is_available = is_available
            if is_available:
                cookie.failure_count = 0
        
        db.session.commit()
        return cookie
    
    @staticmethod
    def cleanup_expired_cookies() -> int:
        """清理过期的Cookie"""
        expired = CookiePool.query.filter(
            CookiePool.expires_at < datetime.utcnow()
        ).all()
        
        count = len(expired)
        for cookie in expired:
            db.session.delete(cookie)
        
        db.session.commit()
        return count
