"""Tests for external markdown prompt loading and configuration fallback."""
import os
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import config


class PromptLoadingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="shockwave-prompt-tests-")
        self.addCleanup(self.temp_dir.cleanup)
        self.prompts_dir = pathlib.Path(self.temp_dir.name) / "prompts"
        self.prompts_dir.mkdir(parents=True, exist_ok=True)

    def test_load_prompt_reads_existing_markdown_file(self):
        idea_file = self.prompts_dir / "idea.md"
        idea_file.write_text("Пользовательский промпт для идеи", encoding="utf-8")
        with patch.object(config, "PROMPTS_DIR", str(self.prompts_dir)):
            content = config.load_prompt("idea.md", "дефолт")
            self.assertEqual(content, "Пользовательский промпт для идеи")

    def test_load_prompt_creates_template_if_missing(self):
        test_file = self.prompts_dir / "custom_task.md"
        self.assertFalse(test_file.exists())
        with patch.object(config, "PROMPTS_DIR", str(self.prompts_dir)):
            content = config.load_prompt("custom_task.md", "Шаблон промпта")
            self.assertEqual(content, "Шаблон промпта")
            self.assertTrue(test_file.exists())
            self.assertEqual(test_file.read_text(encoding="utf-8").strip(), "Шаблон промпта")

    def test_get_prompt_honors_ini_override_if_present(self):
        norm_file = self.prompts_dir / "normalization.md"
        norm_file.write_text("Промпт из файла", encoding="utf-8")
        with patch.object(config, "PROMPTS_DIR", str(self.prompts_dir)):
            # Without INI override
            with patch.object(config, "get_setting", return_value=""):
                content = config.get_prompt("normalization.md", "normalization", "Дефолт")
                self.assertEqual(content, "Промпт из файла")

            # With INI override
            with patch.object(config, "get_setting", return_value="Промпт из config.ini"):
                content = config.get_prompt("normalization.md", "normalization", "Дефолт")
                self.assertEqual(content, "Промпт из config.ini")


if __name__ == "__main__":
    unittest.main()
