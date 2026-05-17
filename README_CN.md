<div align="center">

# OpenRouterFree

**自动发现 OpenRouter 免费大模型，一个接口，全部免费模型。**

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](Dockerfile)

English · [中文文档](#功能特性)

</div>

---

OpenRouterFree 是一个轻量级反向代理，自动发现 [OpenRouter](https://openrouter.ai) 上**所有免费 AI 模型**，并通过**完全兼容 OpenAI 的 API** 暴露出来。只需将任何 OpenAI 客户端指向本服务，即可立即使用免费模型。

## 功能特性

- **自动发现** — 自动获取 OpenRouter 所有免费模型，内存缓存每 10 分钟刷新
- **智能默认** — 自动选择最受欢迎的免费模型（按每周 token 使用量排名）
- **OpenAI 兼容** — 可直接替换任何 OpenAI 客户端库或工具
- **流式支持** — 完整支持 SSE 流式响应，实时输出
- **灵活选型** — 支持自动选择、随机选择或手动指定模型
- **零存储** — API Key 仅透传，服务端不存储任何密钥
- **Docker 就绪** — 一行命令部署

## 快速开始

### 方式一：直接运行

```bash
# 克隆仓库
git clone https://github.com/StanleyChanH/OpenRouterFree.git
cd OpenRouterFree

# 安装依赖（需要 uv）
uv sync

# 启动服务
uv run uvicorn app.main:app
```

### 方式二：Docker

```bash
git clone https://github.com/StanleyChanH/OpenRouterFree.git
cd OpenRouterFree
docker compose up -d
```

服务启动在 `http://localhost:8000`。

## 使用方法

### 对话补全

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer 你的_OPENROUTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "auto",
    "messages": [{"role": "user", "content": "你好！"}]
  }'
```

**模型字段选项：**

| 值 | 行为 |
|----|------|
| `"auto"` 或省略 | 使用最受欢迎的免费模型（按每周 token 排名） |
| `"free-random"` | 从免费模型中随机选择 |
| 具体模型 ID | 使用指定模型（如 `deepseek/deepseek-v4-flash:free`） |

### 流式响应

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer 你的_OPENROUTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "auto",
    "stream": true,
    "messages": [{"role": "user", "content": "给我讲个故事"}]
  }'
```

### 查看免费模型列表

```bash
curl http://localhost:8000/v1/models | jq
```

响应示例：
```json
{
  "object": "list",
  "data": [
    {
      "id": "deepseek/deepseek-v4-flash:free",
      "object": "model",
      "created": 1777000666,
      "owned_by": "openrouter-free-proxy",
      "context_length": 1048576
    }
  ]
}
```

### 查询单个模型

```bash
curl http://localhost:8000/v1/models/deepseek/deepseek-v4-flash:free | jq
```

### 使用 OpenAI SDK（Python）

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="你的_OPENROUTER_KEY"
)

# 自动选择最佳免费模型
response = client.chat.completions.create(
    model="auto",
    messages=[{"role": "user", "content": "你好！"}]
)
print(response.choices[0].message.content)
```

### 配合其他客户端

兼容所有 OpenAI 兼容客户端，只需设置 Base URL：

| 客户端 | Base URL |
|--------|----------|
| ChatGPT-Next-Web | `http://localhost:8000` |
| LobeChat | `http://localhost:8000/v1` |
| LibreChat | `http://localhost:8000/v1` |
| 任意 OpenAI SDK | 设置 `base_url` 为 `http://localhost:8000/v1` |

## 对接 Agent 框架

### OpenClaw

OpenClaw 支持自定义 OpenAI 兼容模型提供者。编辑 `config.yaml`：

```yaml
models:
  providers:
    openrouter-free:
      baseUrl: http://localhost:8000/v1
      apiKey: YOUR_OPENROUTER_KEY

agents:
  defaults:
    model:
      primary: openrouter-free/auto
```

或使用交互式配置：

```bash
openclaw onboard
# 选择 "Custom Provider" → 设置 baseUrl 为 http://localhost:8000/v1
```

模型名设为 `openrouter-free/auto` 自动选择，或 `openrouter-free/deepseek/deepseek-v4-flash:free` 指定模型。

### Hermes

Hermes Agent 支持任意 OpenAI 兼容端点作为自定义提供者。在配置中添加：

```yaml
providers:
  openrouter-free:
    type: openai
    base_url: http://localhost:8000/v1
    api_key: YOUR_OPENROUTER_KEY

default_provider: openrouter-free
default_model: auto
```

Hermes 还可以暴露自身的 OpenAI 兼容 API Server，实现链式调用：`Hermes → OpenRouterFree → OpenRouter`。

### Claude Code

Claude Code 原生使用 Anthropic API 格式。要使用 OpenRouterFree，需要借助转换代理（如 [claude-code-proxy](https://github.com/fuergaosi233/claude-code-proxy)）：

```bash
# 1. 启动 OpenRouterFree
uv run uvicorn app.main:app

# 2. 启动转换代理（在 Anthropic 格式和 OpenAI 格式之间转换）
npx claude-code-proxy --openai-base-url http://localhost:8000/v1 --openai-api-key YOUR_OPENROUTER_KEY

# 3. 将 Claude Code 指向转换代理
export ANTHROPIC_BASE_URL=http://localhost:8080
claude
```

### Cline（VS Code 插件）

1. 打开 VS Code 设置 → 搜索 `cline`
2. 设置 **API Provider** 为 `OpenAI Compatible`
3. 设置 **Base URL** 为 `http://localhost:8000/v1`
4. 设置 **API Key** 为你的 OpenRouter Key
5. 设置 **Model** 为 `auto`

### Cursor

1. 打开设置 → **Models**
2. 添加 **OpenAI API Compatible** 模型
3. 设置 **Base URL** 为 `http://localhost:8000/v1`
4. 设置 **API Key** 为你的 OpenRouter Key
5. 模型名设为 `auto` 或具体的免费模型 ID

### Aider

```bash
pip install aider-chat
aider --openai-api-base http://localhost:8000/v1 \
      --openai-api-key YOUR_OPENROUTER_KEY \
      --model openai/auto
```

### OpenHands

设置环境变量：

```bash
export LLM_MODEL="auto"
export LLM_API_KEY="YOUR_OPENROUTER_KEY"
export LLM_BASE_URL="http://localhost:8000/v1"
```

## 配置项

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `PORT` | `8000` | 服务监听端口 |
| `CACHE_TTL` | `600` | 模型缓存刷新间隔（秒） |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | OpenRouter API 基础 URL |

通过环境变量或 `.env` 文件设置（参考 [.env.example](.env.example)）。

## API 参考

### `POST /v1/chat/completions`

OpenAI 兼容的对话补全端点。支持流式（`stream: true`）和非流式响应。

### `GET /v1/models`

返回当前所有可用免费模型，按每周 token 使用量降序排列（最受欢迎的在前面）。

### `GET /v1/models/{model_id}`

返回指定免费模型的详细信息。

## 获取 OpenRouter API Key

1. 在 [openrouter.ai](https://openrouter.ai) 注册账号
2. 前往 [Keys](https://openrouter.ai/keys) 创建新密钥
3. 免费模型不消耗额度，但仍需 API Key

## 开发

```bash
# 安装开发依赖
uv sync

# 运行单元测试
uv run pytest -v

# 开发模式启动（自动重载）
uv run uvicorn app.main:app --reload

# 运行集成测试（需要先启动服务并设置 OPENROUTER_API_KEY）
OPENROUTER_API_KEY=你的key PYTHONUTF8=1 uv run python test_all.py
```

## 项目结构

```
OpenRouterFree/
├── app/
│   ├── config.py         # 环境变量配置
│   ├── models.py         # 模型缓存、筛选、排序
│   ├── proxy.py          # 请求转发（流式 + 非流式）
│   └── main.py           # FastAPI 应用与路由
├── tests/
│   ├── conftest.py       # 测试夹具
│   ├── test_models.py    # 模型缓存单元测试
│   ├── test_proxy.py     # 代理解析测试
│   └── test_api.py       # API 路由集成测试
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── test_all.py           # 完整集成测试脚本
```

## 许可证

[MIT](LICENSE) © StanleyChanH
