"""Skill management for nanoagent.

Skills are instruction templates that define the agent's behavior.
Currently supports 'instruction' type skills (YAGNI: code-type skills later).
"""

import json
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Skill:
    name: str
    description: str
    type: str = "instruction"
    instructions: str = ""
    tools: list[str] = field(default_factory=list)


class SkillManager:
    """Loads and manages skills from a directory of .skill.json files."""

    def __init__(self, skill_dir: str = "skills"):
        self.skill_dir = skill_dir
        self._skills: dict[str, Skill] = {}

    def load_skills(self) -> None:
        if not os.path.isdir(self.skill_dir):
            return
        for filename in os.listdir(self.skill_dir):
            if not filename.endswith(".skill.json"):
                continue
            path = os.path.join(self.skill_dir, filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                skill = Skill(
                    name=data["name"],
                    description=data.get("description", ""),
                    type=data.get("type", "instruction"),
                    instructions=data.get("instructions", ""),
                    tools=data.get("tools", []),
                )
                self._skills[skill.name] = skill
            except (json.JSONDecodeError, KeyError, IOError) as e:
                print(f"Warning: failed to load skill '{filename}': {e}")

    def get_skill(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)

    def list_skills(self) -> list[dict]:
        return [
            {"name": s.name, "description": s.description, "type": s.type}
            for s in self._skills.values()
        ]

    def get_all_instructions(self) -> str:
        return "\n\n".join(s.instructions for s in self._skills.values() if s.instructions)

    def reload_skills(self) -> None:
        self._skills.clear()
        self.load_skills()
