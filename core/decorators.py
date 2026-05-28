"""
权限控制装饰器模块
"""
from functools import wraps
from flask import jsonify, request, redirect, url_for, flash
from flask_login import current_user


def _is_api_request():
    """判断是否为 API 请求"""
    return request.path.startswith('/api')


# 权限描述映射（用于友好提示）
PERMISSION_LABELS = {
    'write_articles': '文章管理',
    'write_ai_news': 'AI资讯管理',
    'write_education': '教育资讯管理',
    'write_finance': '投融资/财报管理',
    'write_reports': '周报管理',
    'manage_crawl': '采集管理',
    'manage_settings': '系统设置',
}


def admin_required(f):
    """要求管理员及以上角色（super_admin 或 admin）"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if _is_api_request():
                return jsonify({'code': 401, 'message': '请先登录'}), 401
            return redirect(url_for('auth.login'))
        if not current_user.is_admin:
            if _is_api_request():
                return jsonify({'code': 403, 'message': '权限不足，仅管理员可执行此操作'}), 403
            flash('权限不足，仅管理员可执行此操作', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


def super_admin_required(f):
    """要求超级管理员角色"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if _is_api_request():
                return jsonify({'code': 401, 'message': '请先登录'}), 401
            return redirect(url_for('auth.login'))
        if current_user.role != 'super_admin':
            if _is_api_request():
                return jsonify({'code': 403, 'message': '权限不足，仅超级管理员可执行此操作'}), 403
            flash('权限不足，仅超级管理员可执行此操作', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


def require_permission(perm_name):
    """
    要求指定模块权限。
    管理员（super_admin / admin）自动通过。
    普通用户需被分配对应权限。
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                if _is_api_request():
                    return jsonify({'code': 401, 'message': '请先登录'}), 401
                return redirect(url_for('auth.login'))
            if not current_user.has_permission(perm_name):
                label = PERMISSION_LABELS.get(perm_name, perm_name)
                if _is_api_request():
                    return jsonify({
                        'code': 403,
                        'message': f'权限不足，需要"{label}"权限才可执行此操作'
                    }), 403
                flash(f'权限不足，需要"{label}"权限才可执行此操作', 'error')
                return redirect(url_for('main.index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def write_required(f):
    """要求写入权限（管理员或有任意写入权限的普通用户）—— 保留用于兼容"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if _is_api_request():
                return jsonify({'code': 401, 'message': '请先登录'}), 401
            return redirect(url_for('auth.login'))
        if not current_user.can_write:
            if _is_api_request():
                return jsonify({'code': 403, 'message': '权限不足，您仅有浏览权限'}), 403
            flash('权限不足，您仅有浏览权限', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function
