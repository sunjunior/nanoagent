# Nanoagent 用户使用指南

> 轻量级 Agent 系统，具备记忆、Skill 和 MCP 动态注册能力

## 概述

Nanoagent 是一个基于 OpenAI API 的轻量级 Agent 系统，三大核心能力：

| 能力 | 说明 |
|------|------|
| 🧠 **记忆** | 对话历史 + 长期记忆（key-value），存储于 SQLite |
| 🧩 **Skill** | 指令模板式能力定义，JSON 文件热加载 |
| 🔌 **MCP** | 动态服务注册与发现，MCP 服务自动转为 Agent 工具 |

---

## 快速开始

### 环境要求

- Python 3.10+
- `openai` Python 包

```bash
pip install openai
```

### 启动 MCP 注册中心（可选）

如果需要使用 MCP 动态服务发现功能：

```bash
python mcp_registry.py
```

### 启动 MCP 服务（可选）

例如启动温度查询服务（在另一个终端）：

```bash
python mcp_services/temperature_mcp.py
```

该服务启动时会自动向注册中心注册，无需手动配置。

### 运行 Agent

```bash
python agent.py "你好，请介绍一下你自己"
```

或者传入一个任务：

```bash
python agent.py "帮我创建一个 hello.py 文件"
```

---

## 三大能力详解

### 🧠 记忆系统

记忆分为两层，自动管理，无需手动干预。

**会话记忆：**

- Agent 自动记录每次对话的用户消息和 AI 回复
- 启动时自动加载最近 50 条消息作为上下文
- 存储在 `nanoagent.db`（SQLite 数据库）

**长期记忆（由 AI 自主管理）：**

Agent 可以通过调用以下工具自主管理长期记忆：

| 工具 | 功能 | 示例场景 |
|------|------|---------|
| `remember(key, value)` | 存储一条信息 | 记住用户的名字、偏好 |
| `recall(key)` | 按 key 检索 | 查询之前记住的信息 |
| `recall_all()` | 获取所有信息 | 加载全部已知上下文 |
| `forget(key)` | 删除一条信息 | 删除过时信息 |

这些工具可作为 function calling 被 LLM 调用，也可通过环境变量 `NANOAGENT_DB` 指定数据库路径。

### 🧩 Skill 系统

Skill 是 JSON 格式的指令模板文件，放在 `skills/` 目录下。

**定义格式**（`skills/basic.skill.json`）：

```json
{
  "name": "basic",
  "description": "基础能力",
  "type": "instruction",
  "instructions": "你是一个有用的助手。你可以执行 bash 命令、读写文件。\n请保持回答简洁准确。",
  "tools": []
}
```

**字段说明：**

| 字段 | 说明 |
|------|------|
| `name` | Skill 名称，唯一标识 |
| `description` | 描述信息 |
| `type` | 当前仅支持 `instruction`（预留 `code` 扩展） |
| `instructions` | system prompt 指令内容，合并后注入 LLM |
| `tools` | 关联工具列表（当前为空，由 MCP + 核心提供） |

**使用方法：**

1. 在 `skills/` 目录下创建 `*.skill.json` 文件
2. Agent 启动时自动加载所有 skill
3. 所有 skill 的 `instructions` 自动合并为 system prompt
4. 调用 `reload_skills()` 可热加载（无需重启 Agent）

### 🔌 MCP 系统

MCP（Model Context Protocol）系统允许外部服务动态注册为 Agent 的工具。

**架构：**

```
MCP 注册中心 (mcp_registry.py)    ← 中央服务注册表
       ↕ 注册 / 发现
Agent  (agent.py)                 ← 自动发现 MCP 服务
       ↕ 调用
MCP 服务 (mcp_services/)          ← 外部微服务
```

**内置服务：**

温度查询服务 (`mcp_services/temperature_mcp.py`)：
- 注册时声明自己的 tool schema（`query_temperature`）
- Agent 自动发现并作为 function calling 工具使用
- 注册信息包含 tools 字段，无需手动配置

**添加新 MCP 服务：**

在 `mcp_services/` 下创建新服务，启动时向注册中心 POST 注册信息，包含：

```python
payload = {
    "name": "my_service",
    "endpoint": "http://127.0.0.1:9000",
    "health": "http://127.0.0.1:9000/health",
    "description": "我的服务说明",
    "tools": [
        {
            "name": "my_tool",
            "description": "工具功能说明",
            "parameters": {
                "type": "object",
                "properties": {
                    "param1": {"type": "string", "description": "参数说明"}
                },
                "required": ["param1"]
            }
        }
    ]
}
```

Agent 启动时会自动调用 `GET /services` 获取所有服务的 tools，合并到 function calling 列表中。

---

## 环境变量配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `OPENAI_API_KEY` | (内置测试 key) | OpenAI API key |
| `OPENAI_BASE_URL` | `https://generativelanguage.googleapis.com/v1beta/openai` | API base URL |
| `OPENAI_MODEL` | `gemini-2.5-flash` | 模型名称 |
| `MCP_REGISTRY_URL` | `http://127.0.0.1:5000` | MCP 注册中心地址 |
| `NANOAGENT_DB` | `nanoagent.db` | SQLite 数据库路径 |
| `NANOAGENT_SKILL_DIR` | `skills/` | Skill 文件目录 |

示例：

```bash
OPENAI_MODEL=gpt-4o MCP_REGISTRY_URL=http://my-registry:5000 python agent.py "任务"
```

---

## 目录结构

```
├── __init__.py                  # 包初始化
├── agent.py                     # 主 Agent 入口
├── memory.py                    # SQLite 记忆管理
├── skill_manager.py             # Skill 加载与管理
├── mcp_registry.py              # MCP 注册中心
├── mcp_client.py                # MCP 服务发现客户端
├── skills/
│   └── basic.skill.json         # 基础 skill 定义
├── mcp_services/
│   ├── __init__.py
│   └── temperature_mcp.py       # 温度查询 MCP 服务
└── tests/
    ├── test_memory.py           # 记忆测试
    ├── test_skill_manager.py    # Skill 测试
    ├── test_mcp_client.py       # MCP 客户端测试
    ├── test_mcp_registry.py     # 注册中心测试
    ├── test_temperature_mcp.py  # 温度服务测试
    └── test_agent.py            # Agent 集成测试
```

---

## 运行测试

```bash
# 运行全部测试
python -m unittest discover -s tests -v

# 运行特定模块测试
python -m unittest tests.test_memory -v
python -m unittest tests.test_skill_manager -v
python -m unittest tests.test_mcp_client -v
python -m unittest tests.test_agent -v
```

---

## 扩展指南

### 添加新 Skill

1. 在 `skills/` 下创建 `your_skill.skill.json`
2. 按 JSON 格式编写指令模板
3. 重启 Agent 或调用 `reload_skills()`

### 添加新 MCP 服务

1. 在 `mcp_services/` 下创建 `your_service.py`
2. 启动时调用注册中心 API 注册自身（含 tools schema）
3. 启动服务监听端口
4. Agent 自动发现并集成

### 添加新的核心工具

在 `agent.py` 中：
1. 在 `CORE_TOOLS` 列表添加 tool schema
2. 在 `CORE_FUNCTIONS` 字典添加对应的处理函数

---

## 故障排查

**Agent 无法启动：**
- 检查 `OPENAI_API_KEY` 和 `OPENAI_BASE_URL` 配置
- 确认 `openai` 包已安装

**MCP 服务注册失败：**
- 确认注册中心已启动：`curl http://127.0.0.1:5000/health`
- 检查 `MCP_REGISTRY_URL` 配置

**Skill 未加载：**
- 确认 `*.skill.json` 文件在 `skills/` 目录下
- 检查 JSON 格式是否合法
- 查看 Agent 启动日志中的 Warning 信息

---

## 技术栈

- Python 3 标准库（`sqlite3`, `http.server`, `urllib`, `json`）
- OpenAI SDK（`openai`）
- 存储：SQLite3
- 通信：HTTP REST
