"""Nanoagent - Lightweight agent with memory, skills, and MCP support."""

import json
import os
import subprocess
from openai import OpenAI

from memory import Memory
from skill_manager import SkillManager
from mcp_client import MCPClient

# -- Configuration --
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "AIzaSyD-i_P3PiiRhty4uftqk1fX2VfxCtky7yw")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gemini-2.5-flash")
MCP_REGISTRY_URL = os.environ.get("MCP_REGISTRY_URL", "http://127.0.0.1:5000")
DB_PATH = os.environ.get("NANOAGENT_DB", "nanoagent.db")
SKILL_DIR = os.environ.get("NANOAGENT_SKILL_DIR", os.path.join(os.path.dirname(__file__), "skills"))

client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

# -- Subsystems --
memory = Memory(DB_PATH)
skill_manager = SkillManager(SKILL_DIR)
mcp_client = MCPClient(MCP_REGISTRY_URL)

# -- Core tools (always available) --
CORE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "execute_bash",
            "description": "Execute a bash command",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write to a file",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
            },
        },
    },
]

MEMORY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "Store a piece of information in long-term memory (key-value)",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Memory key"},
                    "value": {"type": "string", "description": "Memory value"},
                },
                "required": ["key", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall",
            "description": "Retrieve a value from long-term memory by key",
            "parameters": {
                "type": "object",
                "properties": {"key": {"type": "string", "description": "Memory key"}},
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall_all",
            "description": "Retrieve all long-term memory as a JSON object",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "forget",
            "description": "Delete a piece of information from long-term memory",
            "parameters": {
                "type": "object",
                "properties": {"key": {"type": "string", "description": "Memory key to delete"}},
                "required": ["key"],
            },
        },
    },
]


# -- Core function implementations --
def execute_bash(command: str) -> str:
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return (result.stdout + result.stderr).strip()


def read_file(path: str) -> str:
    with open(path, "r") as f:
        return f.read()


def write_file(path: str, content: str) -> str:
    with open(path, "w") as f:
        f.write(content)
    return f"Wrote to {path}"


def _remember(key: str, value: str) -> str:
    memory.remember(key, value)
    return f"Stored: {key} = {value}"


def _recall(key: str) -> str:
    val = memory.recall(key)
    return val if val is not None else f"No memory found for key '{key}'"


def _recall_all() -> str:
    return json.dumps(memory.recall_all(), ensure_ascii=False)


def _forget(key: str) -> str:
    memory.forget(key)
    return f"Forgot: {key}"


CORE_FUNCTIONS = {
    "execute_bash": execute_bash,
    "read_file": read_file,
    "write_file": write_file,
    "remember": _remember,
    "recall": _recall,
    "recall_all": _recall_all,
    "forget": _forget,
}


def build_system_prompt() -> str:
    parts = []
    skill_manager.load_skills()
    instructions = skill_manager.get_all_instructions()
    if instructions:
        parts.append(instructions)

    long_term = memory.recall_all()
    if long_term:
        parts.append(f"## Known Information\n{json.dumps(long_term, ensure_ascii=False, indent=2)}")

    return "\n\n".join(parts) if parts else "You are a helpful assistant. Be concise."


def build_tools() -> list[dict]:
    tools = list(CORE_TOOLS)
    try:
        mcp_tools = mcp_client.get_openai_tools()
        tools.extend(mcp_tools)
    except Exception:
        pass
    return tools


def run_agent(user_message: str, max_iterations: int = 10) -> str:
    memory.add_message("user", user_message)
    messages = [{"role": "system", "content": build_system_prompt()}]
    messages.extend(memory.get_recent_messages())
    tools = build_tools()

    for _ in range(max_iterations):
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            tools=tools,
        )
        message = response.choices[0].message
        messages.append(message)
        if message.content:
            memory.add_message("assistant", message.content)

        if not message.tool_calls:
            return message.content or ""

        for tool_call in message.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            print(f"[Tool] {name}({args})")

            if name in CORE_FUNCTIONS:
                result = CORE_FUNCTIONS[name](**args)
            else:
                # Try MCP services
                services = mcp_client.discover_services()
                result = mcp_client.call_service_tool(services, name, args)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })
            memory.add_message("tool", result)

    return "Max iterations reached"


if __name__ == "__main__":
    import sys
    task = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Hello"
    print(run_agent(task))
