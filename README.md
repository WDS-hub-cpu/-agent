<img width="1865" height="605" alt="image" src="https://github.com/user-attachments/assets/01faa89e-9ea2-4fa1-a017-bde53f19cb1c" />
# 销售数据 API + AI 对话服务

基于 **FastAPI + SQLAlchemy + MySQL + LangChain + Qwen + Redis + JWT** 的前后端分离项目。

---

## 📁 项目结构

```
deepresearch/
├── .env                          # 环境变量（数据库/Redis/Qwen/JWT）
├── README.md                     # 项目说明
│
├── backend/                      # 🔧 后端 — FastAPI
│   ├── main.py                   #   入口：路由注册、CORS、JWT 中间件、/login
│   ├── chat.py                   #   /chat 对话 + /chat/sessions 会话管理
│   ├── agent.py                  #   ReAct Agent（Qwen + 工具调用）
│   ├── tools.py                  #   工具函数：query_sales_data / calculate_trend
│   ├── auth.py                   #   认证：JWT 签发/验证、角色权限、contextvars
│   ├── memory.py                 #   Redis 持久化记忆（自动降级）
│   ├── models.py                 #   ORM 模型（SQLAlchemy）
│   ├── database.py               #   数据库连接
│   ├── config.py                 #   配置加载
│   ├── requirements.txt          #   Python 依赖
│   └── sqltable/                 #   SQL 脚本
│
└── frontend/                     # 🎨 前端 — HTML/CSS/JS
    ├── index.html                #   登录页 + 聊天页（一键切换）
    ├── css/
    │   └── style.css             #   现代化 UI + 登录遮罩
    └── js/
        └── app.js                #   JWT 认证 + 聊天交互 + 会话管理
```

---

## 🚀 快速启动

### 1. 环境要求

- Python 3.10+
- MySQL 5.7 / 8.0
- Redis（可选，不可用时自动降级内存存储）
- 阿里云 DashScope API Key

### 2. 安装依赖

```bash
cd deepresearch
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r backend/requirements.txt
```

### 3. 配置 `.env`

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=你的密码
DB_NAME=demo

QWEN_API_KEY=sk-你的key
QWEN_MODEL=qwen-plus
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

REDIS_HOST=localhost
REDIS_PORT=6379

JWT_SECRET=你的JWT密钥
```

### 4. 初始化数据库

```bash
mysql -u root -p < backend/sqltable/01_create_table.sql
mysql -u root -p < backend/sqltable/02_insert_test_data.sql
```

### 5. 启动 Redis（可选）

```bash
# Windows 安装后自动启动，或手动：
"C:\Program Files\Redis\redis-server.exe"
```

### 6. 启动后端

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 7. 启动前端

```bash
cd frontend
python -m http.server 5500
```

打开 `http://localhost:5500`

---

## 🔐 登录认证

| 用户名 | 密码 | 角色 | 数据权限 |
|--------|------|------|----------|
| `admin` | `admin123` | 管理员 | 全部大区 |
| `east` | `east123` | 华东区专员 | 仅华东 |
| `south` | `south123` | 华南区专员 | 仅华南 |
| `north` | `north123` | 华北区专员 | 仅华北 |
| `central` | `central123` | 华中区专员 | 仅华中 |
| `west` | `west123` | 西南区专员 | 仅西南 |
| `northwest` | `nw123` | 西北区专员 | 仅西北 |

> 前端点登录遮罩上的快捷按钮即可一键填充。

---

## 🔌 API 接口

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| POST | `/login` | 无 | 登录获取 JWT Token |
| GET | `/health` | 无 | 健康检查 |
| POST | `/chat` | Bearer | ReAct Agent 对话（带角色权限） |
| GET | `/chat/sessions` | Bearer | 会话列表 |
| GET | `/chat/session/{id}` | Bearer | 会话统计 |
| GET | `/chat/session/{id}/messages` | Bearer | 会话消息 |
| DELETE | `/chat/session/{id}` | Bearer | 删除会话 |

---

## 🧪 验证权限

```bash
# 1. 登录
curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"username":"east","password":"east123"}'
# → 得到 access_token

# 2. 华东专员查华北 → 被拒
curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"message":"查华北区销售额"}'

# 3. 华东专员查华东 → 通过
curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"message":"查华东区销售额"}'
```

---

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI |
| ORM | SQLAlchemy 2.0 |
| 数据库 | MySQL |
| 缓存/记忆 | Redis（自动降级内存） |
| AI 模型 | Qwen（DashScope） |
| Agent 框架 | LangChain 1.3+ (create_agent) |
| 认证 | JWT (pyjwt) + contextvars |
| 前端 | HTML / CSS / JS（零框架） |

---

## ⚠️ 常见问题

| 问题 | 解决 |
|------|------|
| `No module named 'pymysql'` | `pip install -r backend/requirements.txt` |
| Redis 连接失败 | 安装并启动 Redis，或使用内存降级模式 |
| `Could not import module "main"` | 必须在 `backend/` 目录下运行 uvicorn |
| 前端无法调用后端 | 检查 `8000` 端口，检查 CORS |
| Token 过期 | 重新登录获取新 Token |
