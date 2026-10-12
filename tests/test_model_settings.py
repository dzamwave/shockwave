"""Model/settings regressions using temporary files and fictional downloads."""
import contextlib
import importlib.metadata
import importlib.util
import io
import os
import pathlib
import sys
import tempfile
import threading
import types
import unittest
import zipfile
from unittest.mock import patch

import numpy as np


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_source(name, filename, dependencies, virtual_file=None):
    spec = importlib.util.spec_from_file_location(name, ROOT / "src" / filename)
    module = importlib.util.module_from_spec(spec)
    if virtual_file:
        module.__file__ = str(virtual_file)
    with patch.dict(sys.modules, dependencies):
        spec.loader.exec_module(module)
    return module


class ModelSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="shockwave-model-tests-")
        self.addCleanup(self.temp.cleanup)
        self.folder = pathlib.Path(self.temp.name)
        self.capture = contextlib.redirect_stdout(io.StringIO())
        self.capture.__enter__()
        self.addCleanup(self.capture.__exit__, None, None, None)
        # A clean fictional environment prevents any real credentials/profile use.
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.dotenv = types.ModuleType("dotenv")
        self.dotenv.load_dotenv = lambda *args, **kwargs: None
        self.secret_writes = []
        self.dotenv.set_key = lambda *args, **kwargs: self.secret_writes.append(args)
        self.ini = self.folder / "config.ini"
        self.ini.write_text(
            "# user comment\n[Recognition]\nengine = gigaam\n"
            "gigaam_quantization = int8\nwake_word = мега\n"
            "[Interface]\nlanguage = ru\nhotkey = alt+space\n"
            "[Custom]\nuser_setting = keep me\n[Prompts]\nai_task = Keep 100%% of data\n",
            encoding="utf-8",
        )
        self.config = self.reload_config()
        hub = types.ModuleType("huggingface_hub")
        hub.snapshot_download = lambda **kwargs: None
        self.manager = load_source("settings_manager", "model_manager.py", {
            "config": self.config, "dotenv": self.dotenv, "huggingface_hub": hub,
        })
        self.launcher = load_source("settings_launcher", "launcher.py", {
            "config": self.config, "dotenv": self.dotenv,
        })
        with patch.object(importlib.metadata, "version", importlib.metadata.version):
            self.audio_module = load_source("settings_audio", "audio_engine.py", {"config": self.config, "sounddevice": types.ModuleType("sounddevice")})
        self.wake = load_source("settings_wake", "wake_word.py", {
            "config": self.config, "vosk": types.ModuleType("vosk"), "sounddevice": types.ModuleType("sounddevice"),
        })

    def reload_config(self):
        with patch("os.path.abspath", wraps=os.path.abspath) as absolute:
            # The module sees only a temporary cwd/config, never the project .env.
            absolute.side_effect = lambda value: str(self.folder / value) if value in ("config.ini", ".env", "glossary.txt") else absolute._mock_wraps(value)
            return load_source("settings_config", "config.py", {"dotenv": self.dotenv}, self.folder / "src" / "config.py")

    def test_menu_engine_choice_survives_restart_and_preserves_other_settings(self):
        with patch("builtins.input", side_effect=["1", ""]):
            self.launcher.setup_stt("ru")
        reloaded = self.reload_config()
        self.assertEqual(reloaded.STT_ENGINE, "whisper")
        self.assertEqual(reloaded.HOTKEY, "alt+space")
        text = self.ini.read_text(encoding="utf-8")
        self.assertIn("# user comment", text)
        self.assertIn("user_setting = keep me", text)
        self.assertIn("ai_task = Keep 100%% of data", text)
        self.assertEqual(self.secret_writes, [])

    def test_wake_word_menu_saves_ini_without_writing_secrets(self):
        with patch("builtins.input", side_effect=["Шоквейв", ""]):
            self.launcher.setup_wake_word("ru")
        self.assertEqual(self.reload_config().WAKE_WORD, "шоквейв")
        self.assertEqual(self.secret_writes, [])

    def test_save_failure_keeps_file_and_active_setting(self):
        original = self.ini.read_bytes()
        with patch("os.replace", side_effect=PermissionError("fictional write failure")):
            with self.assertRaises(PermissionError):
                self.config.save_setting("STT_ENGINE", "whisper")
        self.assertEqual(self.ini.read_bytes(), original)
        self.assertEqual(self.config.STT_ENGINE, "gigaam")
        self.assertEqual(list(self.folder.glob("tmp*")), [])

    def test_save_supports_flat_and_missing_config(self):
        self.ini.write_text("# flat\nengine = gigaam\ncustom = keep\n", encoding="utf-8")
        self.config.save_setting("STT_ENGINE", "whisper")
        self.assertEqual(self.reload_config().STT_ENGINE, "whisper")
        self.assertIn("custom = keep", self.ini.read_text(encoding="utf-8"))
        self.ini.unlink()
        self.config.save_setting("APP_LANGUAGE", "en")
        self.assertEqual(self.reload_config().APP_LANGUAGE, "en")

    def test_language_menu_choice_survives_restart(self):
        with (
            patch.object(self.launcher, "ensure_env_exists"),
            patch.object(self.launcher, "clear_screen"),
            patch.object(self.launcher, "print_banner"),
            patch("builtins.input", side_effect=["6", "7"]),
        ):
            with self.assertRaises(SystemExit):
                self.launcher.menu()
        self.assertEqual(self.reload_config().APP_LANGUAGE, "en")
        self.assertEqual(self.secret_writes, [])

    def test_save_preserves_crlf_comments_and_multiline_prompts(self):
        content = "[Recognition]\r\nengine = gigaam\r\n# user note\r\n[Prompts]\r\nai_task = first\r\n    second\r\n"
        self.ini.write_bytes(content.encode("utf-8"))
        self.config.save_setting("STT_ENGINE", "whisper")
        self.assertEqual(self.ini.read_bytes(), content.replace("engine = gigaam", "engine = whisper").encode("utf-8"))
        self.assertEqual(self.reload_config().LLM_PROMPT_AI_TASK, "first\nsecond")

    def test_old_environment_remains_fallback_when_ini_has_no_setting(self):
        self.ini.write_text("[Custom]\nkeep = yes\n", encoding="utf-8")
        os.environ["STT_ENGINE"] = "whisper"
        os.environ["WAKE_WORD"] = "старое"
        reloaded = self.reload_config()
        self.assertEqual(reloaded.STT_ENGINE, "whisper")
        self.assertEqual(reloaded.WAKE_WORD, "старое")

    def test_gigaam_readiness_matches_selected_precision_and_complete_set(self):
        target = pathlib.Path(self.config.GIGAAM_DIR)
        target.mkdir(parents=True)
        for component in ("encoder", "decoder", "joint"):
            (target / f"v3_e2e_rnnt_{component}_int8.onnx").write_bytes(b"fictional")
        (target / "v3_e2e_rnnt_vocab.txt").write_text("fictional", encoding="utf-8")
        self.assertTrue(self.manager.is_gigaam_downloaded())
        self.config.GIGAAM_QUANTIZATION = "float32"
        self.assertFalse(self.manager.is_gigaam_downloaded())
        for component in ("encoder", "decoder", "joint"):
            (target / f"v3_e2e_rnnt_{component}.onnx").write_bytes(b"fictional")
        self.assertTrue(self.manager.is_gigaam_downloaded())
        (target / "v3_e2e_rnnt_joint.onnx").unlink()
        self.assertFalse(self.manager.is_gigaam_downloaded())

    def test_engine_loader_respects_ini_over_old_environment(self):
        self.config.STT_ENGINE = "gigaam"
        os.environ["STT_ENGINE"] = "whisper"
        self.config.GIGAAM_QUANTIZATION = "float32"
        self.config.ONNX_OPTIMIZE_MEMORY = False
        calls = []
        recognizer = object()
        asr = types.ModuleType("onnx_asr")
        asr.load_model = lambda name, **kwargs: calls.append((name, kwargs)) or recognizer
        engine = self.audio_module.AudioEngine.__new__(self.audio_module.AudioEngine)
        engine.model = None
        engine._model_lock = threading.Lock()
        with patch.dict(sys.modules, {"onnx_asr": asr}):
            self.assertIs(engine.get_or_load_model(), recognizer)
        self.assertEqual(engine.engine_type, "gigaam")
        self.assertEqual(calls[0][1]["quantization"], None)

    def test_model_check_uses_same_engine_as_config(self):
        os.environ["STT_ENGINE"] = "whisper"
        with (
            patch.object(self.manager, "is_gigaam_downloaded", return_value=True),
            patch.object(self.manager, "is_whisper_downloaded", side_effect=AssertionError("wrong engine checked")),
        ):
            self.manager.check_and_prompt(auto_start=False)

    def test_full_gigaam_choice_is_explicit_and_survives_restart(self):
        downloads = []
        with (
            patch.object(self.manager, "is_gigaam_downloaded", return_value=False),
            patch.object(self.manager, "download_gigaam_direct", side_effect=lambda model, **kwargs: downloads.append(kwargs)),
            patch("builtins.input", side_effect=["2", "2"]),
        ):
            self.manager.check_and_prompt(auto_start=False)
        self.assertEqual(self.reload_config().GIGAAM_QUANTIZATION, "float32")
        self.assertEqual(downloads[0]["quant"], "float32")
        self.assertEqual(self.secret_writes, [])

    def test_legacy_empty_quantization_remains_full_precision(self):
        self.ini.write_text("[Recognition]\ngigaam_quantization =\n", encoding="utf-8")
        os.environ["GIGAAM_QUANTIZATION"] = "int8"
        self.assertEqual(self.reload_config().GIGAAM_QUANTIZATION, "float32")
        self.ini.write_text("[Recognition]\nengine = gigaam\n", encoding="utf-8")
        os.environ["GIGAAM_QUANTIZATION"] = ""
        self.assertEqual(self.reload_config().GIGAAM_QUANTIZATION, "float32")

    def test_whisper_language_uses_config_over_legacy_environment(self):
        os.environ["WHISPER_LANGUAGE"] = "en"
        self.config.WHISPER_LANGUAGE = "ru"
        languages = []
        model = types.SimpleNamespace(transcribe=lambda data, language: languages.append(language) or ([types.SimpleNamespace(text="текст")], None))
        engine = self.audio_module.AudioEngine.__new__(self.audio_module.AudioEngine)
        engine.get_or_load_model = lambda: model
        engine.engine_type = "whisper"
        engine.audio_data = [np.ones((16000, 1), dtype=np.float32)]
        engine.sample_rate = 16000
        self.assertEqual(engine.transcribe(), "текст")
        self.assertEqual(languages, ["ru"])

    def make_vosk_files(self, folder):
        for name in ("am/final.mdl", "conf/mfcc.conf", "graph/HCLr.fst", "graph/Gr.fst"):
            path = folder / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"fictional model")

    def fake_download(self, url, destination):
        with zipfile.ZipFile(destination, "w") as archive:
            for name in ("am/final.mdl", "conf/mfcc.conf", "graph/HCLr.fst", "graph/Gr.fst"):
                archive.writestr("vosk-model-small-ru-0.22/" + name, b"fictional model")

    def test_vosk_download_populates_existing_placeholder_folder(self):
        target = pathlib.Path(self.config.VOSK_DIR)
        target.mkdir(parents=True)
        (target / ".gitkeep").write_text("placeholder", encoding="utf-8")
        with patch("urllib.request.urlretrieve", side_effect=self.fake_download):
            self.assertEqual(self.wake.ensure_vosk_model(), str(target))
        self.assertTrue((target / "am/final.mdl").is_file())
        self.assertEqual((target / ".gitkeep").read_text(encoding="utf-8"), "placeholder")
        with patch("urllib.request.urlretrieve", side_effect=AssertionError("unneeded download")):
            self.assertEqual(self.wake.ensure_vosk_model(), str(target))

    def test_existing_vosk_files_are_used_without_download(self):
        target = pathlib.Path(self.config.VOSK_DIR)
        self.make_vosk_files(target)
        with patch("urllib.request.urlretrieve", side_effect=AssertionError("unneeded download")):
            self.assertEqual(self.wake.ensure_vosk_model(), str(target))

    def test_empty_custom_vosk_folder_is_populated(self):
        target = self.folder / "custom" / "vosk"
        target.mkdir(parents=True)
        with patch("urllib.request.urlretrieve", side_effect=self.fake_download):
            self.assertEqual(self.wake.ensure_vosk_model(str(target)), str(target))
        self.assertTrue((target / "am/final.mdl").is_file())

    def test_vosk_failed_publication_restores_placeholder(self):
        target = pathlib.Path(self.config.VOSK_DIR)
        target.mkdir(parents=True)
        (target / ".gitkeep").write_bytes(b"keep")
        rename = os.rename
        def fail_publication(source, destination):
            if pathlib.Path(source).name == "vosk-model-small-ru-0.22":
                raise PermissionError("fictional publish failure")
            return rename(source, destination)
        with patch("urllib.request.urlretrieve", side_effect=self.fake_download), patch("os.rename", side_effect=fail_publication):
            self.assertIsNone(self.wake.ensure_vosk_model())
        self.assertEqual((target / ".gitkeep").read_bytes(), b"keep")
        self.assertEqual(list(target.parent.glob(".vosk-download-*")), [])

    def test_invalid_download_is_not_reported_ready(self):
        target = pathlib.Path(self.config.VOSK_DIR)

        def bad_archive(url, destination):
            with zipfile.ZipFile(destination, "w") as archive:
                archive.writestr("vosk-model-small-ru-0.22/README", "not a model")

        with patch("urllib.request.urlretrieve", side_effect=bad_archive):
            self.assertIsNone(self.wake.ensure_vosk_model())
        self.assertFalse((target / "README").exists())

    def test_incomplete_nonempty_vosk_folder_is_preserved(self):
        target = pathlib.Path(self.config.VOSK_DIR)
        target.mkdir(parents=True)
        (target / "user-file.txt").write_text("keep", encoding="utf-8")
        with patch("urllib.request.urlretrieve", side_effect=AssertionError("do not overwrite user files")):
            self.assertIsNone(self.wake.ensure_vosk_model())
        self.assertEqual((target / "user-file.txt").read_text(), "keep")


if __name__ == "__main__":
    unittest.main()
