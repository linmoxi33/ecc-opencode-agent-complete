import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "bin" / "ecc-opencode-agent-complete"
EX = ROOT / "examples" / "in" / "repo"


def run(*args, cwd=None):
    return subprocess.run([sys.executable, str(BIN), *args],
                          capture_output=True, text=True, cwd=cwd)


class CheckTests(unittest.TestCase):
    def test_help_exits_zero(self):
        p = run("--help")
        self.assertEqual(p.returncode, 0)
        self.assertIn("check", p.stdout)

    def test_missing_subcommand_is_usage_error(self):
        self.assertEqual(run().returncode, 2)

    def test_bad_repo_is_usage_error(self):
        p = run("check", "--repo", "/nonexistent")
        self.assertEqual(p.returncode, 2)
        self.assertIn("config not found", p.stderr)

    def test_fixture_check_reports_gap(self):
        p = run("check", "--repo", str(EX), "--json")
        self.assertEqual(p.returncode, 1)
        data = json.loads(p.stdout)
        self.assertFalse(data["ok"])

    def test_missing_agents_exact(self):
        data = json.loads(run("check", "--repo", str(EX), "--json").stdout)
        self.assertEqual(data["missing_agents"],
                         ["code-simplifier", "comment-analyzer"])

    def test_counts(self):
        data = json.loads(run("check", "--repo", str(EX), "--json").stdout)
        self.assertEqual((data["repo_agents"], data["registered_agents"],
                          data["missing_agent_count"]), (3, 2, 2))

    def test_command_body_refs_are_found(self):
        data = json.loads(run("check", "--repo", str(EX), "--json").stdout)
        self.assertEqual(data["commands_with_missing_agents"],
                         {"review-pr": ["code-simplifier", "comment-analyzer"]})

    def test_instruction_resolution_is_relative_to_config(self):
        data = json.loads(run("check", "--repo", str(EX), "--json").stdout)
        self.assertIn("AGENTS.md", data["missing_instructions"])

    def test_human_output_names_missing_agent(self):
        p = run("check", "--repo", str(EX))
        self.assertEqual(p.returncode, 1)
        self.assertIn("missing agent: code-simplifier", p.stdout)


class EmitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.repo = self.tmp / "repo"
        shutil.copytree(EX, self.repo)
        self.out = self.tmp / "out"

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_emit_writes_prompts_and_config(self):
        p = run("emit", "--repo", str(self.repo), "--out", str(self.out))
        self.assertEqual(p.returncode, 0, p.stderr)
        for name in ("code-simplifier", "comment-analyzer"):
            self.assertTrue((self.out / "prompts" / "agents" / (name + ".txt")).is_file())

    def test_emitted_config_registers_all_agents(self):
        run("emit", "--repo", str(self.repo), "--out", str(self.out))
        cfg = json.loads((self.out / "opencode.json").read_text())
        self.assertIn("code-simplifier", cfg["agent"])
        self.assertEqual(cfg["agent"]["code-simplifier"]["prompt"],
                         "{file:prompts/agents/code-simplifier.txt}")

    def test_manifest_hashes_match_prompt_bytes(self):
        run("emit", "--repo", str(self.repo), "--out", str(self.out))
        man = json.loads((self.out / "manifest.json").read_text())
        self.assertEqual(man["count"], 2)
        for name, digest in man["sha256"].items():
            body = (self.out / "prompts" / "agents" / (name + ".txt")).read_bytes()
            self.assertEqual(hashlib.sha256(body).hexdigest(), digest)

    def test_emit_preserves_existing_entry(self):
        run("emit", "--repo", str(self.repo), "--out", str(self.out))
        cfg = json.loads((self.out / "opencode.json").read_text())
        self.assertEqual(cfg["agent"]["planner"]["prompt"],
                         "{file:prompts/agents/planner.txt}")

    def test_emit_is_idempotent_on_second_run(self):
        run("emit", "--repo", str(self.repo), "--out", str(self.out))
        p = run("emit", "--repo", str(self.repo), "--out", str(self.out), "--json")
        self.assertEqual(json.loads(p.stdout)["count"], 2)

    def test_clean_repo_checks_zero(self):
        cfg = json.loads((self.repo / ".opencode/opencode.json").read_text())
        cfg["instructions"] = []
        cfg["agent"]["code-simplifier"] = {"description": "x", "prompt": "{file:prompts/agents/planner.txt}"}
        cfg["agent"]["comment-analyzer"] = {"description": "x", "prompt": "{file:prompts/agents/planner.txt}"}
        (self.repo / ".opencode/opencode.json").write_text(json.dumps(cfg))
        p = run("check", "--repo", str(self.repo), "--json")
        self.assertEqual(p.returncode, 0)
        self.assertTrue(json.loads(p.stdout)["ok"])


class VerifyInstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "prompts/agents").mkdir(parents=True)
        (self.tmp / "prompts/agents/a.txt").write_text("a")
        (self.tmp / "AGENTS.md").write_text("x")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_good_install_exits_zero(self):
        (self.tmp / "opencode.json").write_text(json.dumps({
            "instructions": ["AGENTS.md"],
            "agent": {"a": {"prompt": "{file:prompts/agents/a.txt}"}}}))
        p = run("verify-install", "--install", str(self.tmp), "--json")
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertTrue(json.loads(p.stdout)["ok"])

    def test_missing_prompt_exits_one(self):
        (self.tmp / "opencode.json").write_text(json.dumps({
            "instructions": [],
            "agent": {"a": {"prompt": "{file:prompts/agents/b.txt}"}}}))
        p = run("verify-install", "--install", str(self.tmp), "--json")
        self.assertEqual(p.returncode, 1)
        self.assertEqual(json.loads(p.stdout)["missing_agent_prompts"],
                         [{"agent": "a", "file": "prompts/agents/b.txt"}])

    def test_missing_instruction_is_reported(self):
        (self.tmp / "opencode.json").write_text(json.dumps({
            "instructions": ["CONTRIBUTING.md"], "agent": {}}))
        p = run("verify-install", "--install", str(self.tmp), "--json")
        self.assertEqual(p.returncode, 1)
        self.assertIn("CONTRIBUTING.md", json.loads(p.stdout)["missing_instructions"])


if __name__ == "__main__":
    unittest.main(verbosity=2)