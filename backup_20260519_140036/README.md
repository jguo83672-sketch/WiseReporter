# WiseReporter - 教育行业信息收集平台

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.8+-green)
![Flask](https://img.shields.io/badge/flask-3.0.0-blue)

## 项目简介

WiseReporter 是一个基于 Flask 的教育行业信息收集平台，用于搜集指定公众号中的教育相关行业动态，包括：

- 教育行业动态
- 教育公司动态
- 投融资动态
- 产品动态
- 教育公司财报
- AI前沿资讯

同时支持生成周报、Cookie池管理、定时任务等功能。

## 功能特性

### 核心功能
- **公众号管理** - 添加、编辑、删除、启用/停用公众号
- **文章采集** - 自动采集公众号文章
- **AI资讯采集** - 采集AI前沿资讯
- **周报生成** - 自动/手动生成Markdown格式周报
- **Cookie池管理** - 维护多个Cookie，支持自动切换

### 数据管理
- 文章分类与标签
- 重要文章标记
- 全文搜索
- 采集日志

### 定时任务
- 自动采集AI资讯
- 自动清理过期Cookie
- 自动生成周报

## 项目结构

```
WiseReporter/
├── app.py              # Flask应用入口
├── config.py            # 配置文件
├── models.py            # 数据库模型
├── scheduler.py         # 定时任务调度器
├── requirements.txt     # 依赖包
├── run.py               # 启动脚本
├── core/                # 核心模块
│   ├── __init__.py
│   ├── cookie_manager.py   # Cookie池管理
│   ├── scraper.py          # 爬虫模块
│   ├── data_store.py       # 数据存储
│   └── report_generator.py # 周报生成
├── routes/              # 路由模块
│   ├── __init__.py
│   ├── main.py           # 主路由
│   ├── api.py            # API路由
│   └── auth.py           # 认证路由
├── templates/           # 模板文件
│   ├── base.html
│   ├── index.html
│   ├── accounts/
│   ├── articles/
│   ├── ai_news/
│   ├── reports/
│   ├── cookies/
│   ├── logs/
│   ├── settings/
│   └── auth/
└── static/              # 静态文件
    ├── css/
    │   └── style.css
    └── js/
        └── main.js
```

## 快速开始

### 环境要求

- Python 3.8+
- SQLite (默认) 或 PostgreSQL/MySQL

### 安装步骤

1. **克隆项目**
```bash
cd WiseReporter
```

2. **创建虚拟环境**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. **安装依赖**
```bash
pip install -r requirements.txt
```

4. **初始化数据库**
```bash
python app.py
# 首次运行会自动创建数据库
```

5. **创建管理员账号**
首次访问 http://localhost:5000/auth/register 注册账号

6. **启动服务**
```bash
python run.py
```

访问 http://localhost:5000 即可使用。

## 配置说明

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| FLASK_CONFIG | 配置环境 | development |
| SECRET_KEY | 密钥 | 自动生成 |
| DATABASE_URL | 数据库URL | sqlite:///wisereporter.db |
| PORT | 端口 | 5000 |

### Cookie池配置

在 `config.py` 中配置：

```python
COOKIE_POOL_SIZE = 5      # Cookie池大小
COOKIE_EXPIRY_HOURS = 24  # Cookie有效期
```

### 爬虫配置

```python
REQUEST_TIMEOUT = 30      # 请求超时（秒）
RETRY_TIMES = 3           # 重试次数
```

## API文档

### 公众号管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/accounts | 获取公众号列表 |
| POST | /api/accounts | 添加公众号 |
| PUT | /api/accounts/{id} | 更新公众号 |
| DELETE | /api/accounts/{id} | 删除公众号 |

### 文章管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/articles | 获取文章列表 |
| PUT | /api/articles/{id}/important | 标记重要 |
| DELETE | /api/articles/{id} | 删除文章 |

### AI资讯

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/ai-news | 获取AI资讯列表 |
| POST | /api/ai-news/crawl | 采集AI资讯 |

### 周报

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/reports | 获取周报列表 |
| POST | /api/reports/generate | 生成周报 |
| POST | /api/reports/{id}/publish | 发布周报 |

### Cookie池

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/cookies | 获取Cookie列表 |
| POST | /api/cookies | 添加Cookie |
| PUT | /api/cookies/{id} | 更新Cookie |
| DELETE | /api/cookies/{id} | 删除Cookie |

## 定时任务

| 任务ID | 执行时间 | 说明 |
|--------|----------|------|
| crawl_ai_news | 每日02:00 | AI资讯采集 |
| cleanup_cookies | 每6小时 | 清理过期Cookie |
| generate_weekly_report | 每周一09:00 | 自动生成周报 |

## 使用说明

### 添加公众号

1. 进入「公众号管理」页面
2. 点击「添加公众号」
3. 填写公众号名称、ID、分类等信息
4. 保存后可以手动采集测试

### 添加Cookie

1. 进入「Cookie池管理」页面
2. 点击「添加Cookie」
3. 粘贴Cookie数据（JSON格式）和User-Agent
4. 设置过期时间（可选）

### 生成周报

1. 进入「周报」页面
2. 点击「生成周报」
3. 设置周期（默认7天）
4. 查看生成的Markdown周报
5. 可以发布或复制内容

## 注意事项

1. **Cookie管理** - 请定期更新Cookie，保持可用性
2. **采集频率** - 建议合理设置采集间隔，避免被封禁
3. **数据备份** - 定期备份数据库
4. **生产部署** - 使用 Gunicorn + Nginx 部署

## 生产部署

### 使用 Gunicorn

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### 使用 Docker

```dockerfile
FROM python:3.9
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt gunicorn
COPY . .
EXPOSE 5000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

## 许可证

MIT License

## 联系方式

如有问题，请提交 Issue。
