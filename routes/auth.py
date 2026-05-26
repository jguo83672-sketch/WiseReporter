"""
认证路由
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User
from core.decorators import super_admin_required

auth_bp = Blueprint('auth', __name__)

# 可分配的权限列表
AVAILABLE_PERMISSIONS = [
    {'key': 'write_articles', 'label': '文章管理', 'desc': '可增删改文章'},
    {'key': 'write_ai_news', 'label': 'AI资讯管理', 'desc': '可增删改AI资讯'},
    {'key': 'write_education', 'label': '教育资讯管理', 'desc': '可增删改教育资讯'},
    {'key': 'write_leidui', 'label': '投融资/财报管理', 'desc': '可增删改投融资资讯'},
    {'key': 'write_reports', 'label': '周报管理', 'desc': '可生成/编辑/删除周报'},
    {'key': 'manage_crawl', 'label': '采集管理', 'desc': '可执行采集任务'},
    {'key': 'manage_settings', 'label': '系统设置', 'desc': '可修改系统设置'},
]

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            if not user.is_active:
                flash('账号已被禁用，请联系管理员', 'error')
                return render_template('auth/login.html')
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.index'))
        
        flash('用户名或密码错误', 'error')
    
    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """注册页面 — 仅超级管理员可在权限管理页面创建用户"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    # 关闭开放注册，引导用户联系管理员
    flash('系统已关闭自主注册，请联系超级管理员创建账号', 'warning')
    return redirect(url_for('auth.login'))

@auth_bp.route('/logout')
@login_required
def logout():
    """退出登录"""
    logout_user()
    return redirect(url_for('auth.login'))


# ==================== 用户管理 API（仅超级管理员） ====================

@auth_bp.route('/api/users', methods=['GET'])
@login_required
def api_list_users():
    """获取所有用户列表"""
    if current_user.role != 'super_admin':
        return jsonify({'code': 403, 'message': '权限不足'}), 403
    
    users = User.query.order_by(User.created_at.asc()).all()
    return jsonify({
        'code': 0,
        'data': {
            'users': [{
                'id': u.id,
                'username': u.username,
                'email': u.email,
                'role': u.role,
                'is_active': u.is_active,
                'permissions': u.get_permissions_list(),
                'created_at': u.created_at.strftime('%Y-%m-%d %H:%M') if u.created_at else None
            } for u in users],
            'available_permissions': AVAILABLE_PERMISSIONS
        }
    })

@auth_bp.route('/api/users', methods=['POST'])
@login_required
def api_create_user():
    """创建新用户（仅超级管理员）"""
    if current_user.role != 'super_admin':
        return jsonify({'code': 403, 'message': '权限不足'}), 403
    
    data = request.json
    if not data:
        return jsonify({'code': 1, 'message': '请提供用户数据'})
    
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()
    role = data.get('role', 'user')
    
    if not username or not email or not password:
        return jsonify({'code': 1, 'message': '用户名、邮箱和密码不能为空'})
    
    if User.query.filter_by(username=username).first():
        return jsonify({'code': 1, 'message': '用户名已存在'})
    
    if User.query.filter_by(email=email).first():
        return jsonify({'code': 1, 'message': '邮箱已被使用'})
    
    if role not in ('super_admin', 'admin', 'user'):
        return jsonify({'code': 1, 'message': '无效的角色'})
    
    user = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
        role=role
    )
    
    # 如果角色是user且有权限配置
    if role == 'user' and data.get('permissions'):
        user.set_permissions(data['permissions'])
    
    db.session.add(user)
    db.session.commit()
    
    return jsonify({
        'code': 0,
        'message': '用户创建成功',
        'data': {'id': user.id, 'username': user.username}
    })

@auth_bp.route('/api/users/<int:user_id>', methods=['PUT'])
@login_required
def api_update_user(user_id):
    """更新用户信息和权限（仅超级管理员）"""
    if current_user.role != 'super_admin':
        return jsonify({'code': 403, 'message': '权限不足'}), 403
    
    user = User.query.get_or_404(user_id)
    data = request.json
    if not data:
        return jsonify({'code': 1, 'message': '请提供更新数据'})
    
    # 不允许修改自己的角色（防止把自己降级）
    if user.id == current_user.id:
        if 'role' in data and data['role'] != 'super_admin':
            return jsonify({'code': 1, 'message': '不能修改自己的超级管理员角色'})
        if 'is_active' in data and not data['is_active']:
            return jsonify({'code': 1, 'message': '不能禁用自己的账号'})
    
    # 更新角色
    if 'role' in data:
        if data['role'] not in ('super_admin', 'admin', 'user'):
            return jsonify({'code': 1, 'message': '无效的角色'})
        user.role = data['role']
    
    # 更新权限（仅对普通用户生效）
    if 'permissions' in data:
        user.set_permissions(data['permissions'])
    
    # 更新邮箱
    if 'email' in data and data['email']:
        existing = User.query.filter(User.email == data['email'], User.id != user_id).first()
        if existing:
            return jsonify({'code': 1, 'message': '邮箱已被使用'})
        user.email = data['email']
    
    # 更新激活状态
    if 'is_active' in data:
        user.is_active = data['is_active']
    
    db.session.commit()
    
    return jsonify({
        'code': 0,
        'message': '更新成功',
        'data': {
            'id': user.id,
            'username': user.username,
            'role': user.role,
            'is_active': user.is_active,
            'permissions': user.get_permissions_list()
        }
    })

@auth_bp.route('/api/users/<int:user_id>/reset-password', methods=['POST'])
@login_required
def api_reset_password(user_id):
    """重置用户密码（仅超级管理员）"""
    if current_user.role != 'super_admin':
        return jsonify({'code': 403, 'message': '权限不足'}), 403
    
    user = User.query.get_or_404(user_id)
    data = request.json
    new_password = data.get('password', '').strip() if data else ''
    
    if not new_password:
        return jsonify({'code': 1, 'message': '请提供新密码'})
    
    user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    
    return jsonify({'code': 0, 'message': f'用户 {user.username} 的密码已重置'})

@auth_bp.route('/api/users/<int:user_id>', methods=['DELETE'])
@login_required
def api_delete_user(user_id):
    """删除用户（仅超级管理员）"""
    if current_user.role != 'super_admin':
        return jsonify({'code': 403, 'message': '权限不足'}), 403
    
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        return jsonify({'code': 1, 'message': '不能删除自己的账号'})
    
    username = user.username
    db.session.delete(user)
    db.session.commit()
    
    return jsonify({'code': 0, 'message': f'用户 {username} 已删除'})
