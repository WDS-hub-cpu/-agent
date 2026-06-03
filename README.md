<img width="1865" height="605" alt="image" src="https://github.com/user-attachments/assets/01faa89e-9ea2-4fa1-a017-bde53f19cb1c" /># DeepResearch
一个基于Qwen的销售分析系统
# 销售数据 API + AI 对话服务
![Uploading image.png…]()

基于 **FastAPI + SQLAlchemy + MySQL + LangChain + Qwen** 的前后端分离项目。

---

## 🚀 快速启动

### 1. 环境要求

- Python 3.10+
- MySQL 5.7 / 8.0
- 阿里云 DashScope API Key（用于 Qwen 大模型）

### 2. 克隆项目 & 创建虚拟环境

```bash
cd deepresearch
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r backend/requirements.txt
```

### 4. 配置环境变量

编辑 `.env` 文件，填入真实信息：

```env
# ===== 数据库配置 =====
DB_HOST=localhost
DB_PORT=3306
DB_USER=
DB_PASSWORD=你的数据库密码
DB_NAME=

# ===== Qwen 大模型配置 =====
# 在 https://dashscope.console.aliyun.com/ 申请
QWEN_API_KEY=sk-你的真实key
# 可选模型: qwen-turbo / qwen-plus / qwen-max
QWEN_MODEL=qwen-plus
```

### 5. 初始化数据库

```bash
# 登录 MySQL 执行建表脚本
mysql -u root -p < backend/sqltable/01_create_table.sql
mysql -u root -p < backend/sqltable/02_insert_test_data.sql
```

### 6. 启动后端

> ⚠️ 必须在 `backend/` 目录下运行，因为 `main.py` 已移至该目录。

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

| 地址 | 说明 |
|------|------|
| `http://localhost:8000/docs` | Swagger 接口文档 |
| `http://localhost:8000/redoc` | ReDoc 接口文档 |

### 7. 启动前端

新开一个终端：

```bash
cd frontend
python -m http.server 5500
```

打开浏览器访问 `http://localhost:5500`

---

## 🔌 API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查，测试数据库连接 |
| POST | `/chat` | AI 对话，传入消息返回大模型回复 |

### `/chat` 请求示例

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "你好"}'
```

### `/chat` 响应示例

```json
{
  "reply": "你好！我是Qwen大模型，有什么可以帮你的吗？"
}
```

---

## 🧪 验证方式

| 方式 | 操作 |
|------|------|
| **Swagger UI** | 打开 `http://localhost:8000/docs` → `POST /chat` → Try it out |
| **前端页面** | 打开 `http://localhost:5500` → 输入消息 → 回车发送 |
| **curl** | `curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" -d '{"message":"你好"}'` |

---

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI |
| ORM | SQLAlchemy 2.0 |
| 数据库 | MySQL |
| AI 模型 | Qwen（阿里云 DashScope） |
| LLM 框架 | LangChain |
| 前端 | 原生 HTML / CSS / JavaScript |
| CORS | 前后端分离，跨域通信 |

---

## ⚠️ 常见问题

### `ModuleNotFoundError: No module named 'pymysql'`
虚拟环境中缺少依赖，执行 `pip install -r backend/requirements.txt`。

### `QWEN_API_KEY` 未生效
确保 `.env` 文件在项目根目录，且 `config.py` 能正确读取（依赖 `python-dotenv`）。

### 前端无法调用后端
检查后端是否启动在 `8000` 端口，前端 `js/app.js` 中的 `API_BASE` 是否匹配。
