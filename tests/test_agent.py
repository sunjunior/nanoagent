import json
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import patch, MagicMock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

openai_module = types.ModuleType("openai")


class DummyOpenAI:
    def __init__(self, *args, **kwargs):
        self.chat = types.SimpleNamespace(
            completions=types.SimpleNamespace(create=lambda *args, **kwargs: None)
        )


openai_module.OpenAI = DummyOpenAI
sys.modules["openai"] = openai_module

import agent


class TestAgent(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "test.db")
        self.skill_dir = os.path.join(self.tmpdir.name, "skills")
        os.makedirs(self.skill_dir)
        # Override agent's memory and skill dir for testing
        agent.memory = agent.Memory(self.db_path)
        agent.skill_manager = agent.SkillManager(self.skill_dir)

    def tearDown(self):
        agent.memory._conn.close()
        self.tmpdir.cleanup()

    def test_execute_bash_and_file_helpers(self):
        result = agent.write_file(os.path.join(self.tmpdir.name, "hello.txt"), "hello")
        self.assertIn("Wrote to", result)
        out = agent.execute_bash(f"cat {os.path.join(self.tmpdir.name, 'hello.txt')}")
        self.assertIn("hello", out)

    def test_remember_and_recall_tools(self):
        result = agent._remember("city", "Beijing")
        self.assertIn("Stored", result)
        result = agent._recall("city")
        self.assertEqual(result, "Beijing")
        result = agent._recall_all()
        self.assertIn("Beijing", result)
        result = agent._forget("city")
        self.assertIn("Forgot", result)
        result = agent._recall("city")
        self.assertIn("No memory found", result)

    def test_build_system_prompt_with_skills(self):
        skill_path = os.path.join(self.tmpdir.name, "skills", "test.skill.json")
        with open(skill_path, "w") as f:
            json.dump({"name": "test", "description": "", "type": "instruction", "instructions": "Be helpful.", "tools": []}, f)
        prompt = agent.build_system_prompt()
        self.assertIn("Be helpful.", prompt)

    def test_run_agent_returns_content(self):
        response_message = types.SimpleNamespace(content="done", tool_calls=[])
        response = types.SimpleNamespace(choices=[types.SimpleNamespace(message=response_message)])

        with patch.object(agent.client.chat.completions, "create", return_value=response) as mocked:
            result = agent.run_agent("Hello")
            self.assertEqual(result, "done")
            mocked.assert_called_once()
