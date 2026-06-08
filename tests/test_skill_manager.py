import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from skill_manager import SkillManager


class TestSkillManager(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.skill_dir = os.path.join(self.tmpdir.name, "skills")
        os.makedirs(self.skill_dir)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _create_skill(self, name: str, data: dict):
        path = os.path.join(self.skill_dir, f"{name}.skill.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def test_load_and_get_skill(self):
        self._create_skill("test", {
            "name": "test",
            "description": "A test skill",
            "type": "instruction",
            "instructions": "Do something.",
            "tools": [],
        })
        mgr = SkillManager(self.skill_dir)
        mgr.load_skills()
        skill = mgr.get_skill("test")
        self.assertIsNotNone(skill)
        self.assertEqual(skill.name, "test")
        self.assertEqual(skill.description, "A test skill")
        self.assertEqual(skill.instructions, "Do something.")
        self.assertEqual(skill.type, "instruction")

    def test_get_nonexistent_skill(self):
        mgr = SkillManager(self.skill_dir)
        mgr.load_skills()
        self.assertIsNone(mgr.get_skill("nope"))

    def test_list_skills(self):
        self._create_skill("a", {"name": "a", "description": "Skill A", "type": "instruction", "instructions": "", "tools": []})
        self._create_skill("b", {"name": "b", "description": "Skill B", "type": "instruction", "instructions": "", "tools": []})
        mgr = SkillManager(self.skill_dir)
        mgr.load_skills()
        skills = mgr.list_skills()
        self.assertEqual(len(skills), 2)
        names = {s["name"] for s in skills}
        self.assertEqual(names, {"a", "b"})

    def test_get_all_instructions(self):
        self._create_skill("a", {"name": "a", "description": "", "type": "instruction", "instructions": "Instr A", "tools": []})
        self._create_skill("b", {"name": "b", "description": "", "type": "instruction", "instructions": "Instr B", "tools": []})
        mgr = SkillManager(self.skill_dir)
        mgr.load_skills()
        combined = mgr.get_all_instructions()
        self.assertIn("Instr A", combined)
        self.assertIn("Instr B", combined)

    def test_reload_skills(self):
        self._create_skill("first", {"name": "first", "description": "", "type": "instruction", "instructions": "", "tools": []})
        mgr = SkillManager(self.skill_dir)
        mgr.load_skills()
        self.assertEqual(len(mgr.list_skills()), 1)

        self._create_skill("second", {"name": "second", "description": "", "type": "instruction", "instructions": "", "tools": []})
        mgr.reload_skills()
        self.assertEqual(len(mgr.list_skills()), 2)

    def test_skip_non_skill_files(self):
        path = os.path.join(self.skill_dir, "notes.txt")
        with open(path, "w") as f:
            f.write("not a skill")
        mgr = SkillManager(self.skill_dir)
        mgr.load_skills()
        self.assertEqual(len(mgr.list_skills()), 0)

    def test_skip_invalid_json(self):
        path = os.path.join(self.skill_dir, "bad.skill.json")
        with open(path, "w") as f:
            f.write("not valid json")
        mgr = SkillManager(self.skill_dir)
        mgr.load_skills()  # should not raise
        self.assertEqual(len(mgr.list_skills()), 0)
