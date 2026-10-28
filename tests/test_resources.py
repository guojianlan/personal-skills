import argparse
import base64
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/github-resources/scripts/github_resources.py"
spec = importlib.util.spec_from_file_location("github_resources", SCRIPT)
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
REAL_API = r.api


def resource():
    return {"id": "example-dev", "name": "示例百炼", "aliases": ["bailian"], "kind": "ai-provider",
            "environment": "development", "scope": "personal-shared", "capabilities": ["llm"],
            "config": {"base_url": "https://example.com/v1", "default_model": "example"},
            "secrets": {"api_key": "test-only-private-value", "connection_url": "postgres://user:password@localhost/db"}}


class FakeGitHub:
    def __init__(self):
        self.data = {"version": 1, "resources": [resource()]}
        self.sha = "sha-one"
        self.private = True
        self.calls = []

    def api(self, path, method="GET", payload=None):
        self.calls.append((path, method))
        if path == "user":
            return {"login": "example"}
        if path == "repos/example/personal-resources":
            return {"full_name": "example/personal-resources", "private": self.private,
                    "default_branch": "main", "permissions": {"pull": True, "push": True},
                    "html_url": "https://github.com/example/personal-resources"}
        if path.startswith("repos/example/personal-resources/contents/catalog.json"):
            if method == "PUT":
                if payload["sha"] != self.sha:
                    raise r.ResourceError("Conflict")
                self.data = json.loads(base64.b64decode(payload["content"]))
                self.sha = "sha-two"
                return {"commit": {"sha": "commit-two"}}
            raw = json.dumps(self.data).encode()
            return {"size": len(raw), "content": base64.b64encode(raw).decode(), "sha": self.sha}
        raise AssertionError("Unexpected API path")


class ResourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.gh = FakeGitHub()
        self.p1 = patch.object(r, "api", self.gh.api)
        self.p1.start()
        self.addCleanup(self.p1.stop)
        self.p2 = patch.dict(os.environ, {"GITHUB_RESOURCES_CONFIG": str(self.root / "binding.json"), "GITHUB_RESOURCES_REPO": ""})
        self.p2.start()
        self.addCleanup(self.p2.stop)

    def args(self, command, **kw):
        return argparse.Namespace(command=command, repo=None, **kw)

    def test_default_repository_and_metadata_search(self):
        result = r.run(self.args("search", query="百炼"))
        self.assertEqual(result["count"], 1)
        self.assertNotIn("test-only-private-value", json.dumps(result))
        self.assertEqual(result["coverage"], "complete catalog; metadata only")

    def test_search_does_not_match_secret_values(self):
        self.assertEqual(r.run(self.args("search", query="test-only-private-value"))["count"], 0)

    def test_show_masks_all_secrets(self):
        result = r.run(self.args("show", id="example-dev"))
        self.assertEqual(set(result["resource"]["secrets"].values()), {"[REDACTED]"})
        self.assertNotIn("user:password", json.dumps(result))

    def test_public_repo_rejected_before_read(self):
        self.gh.private = False
        with self.assertRaises(r.ResourceError):
            r.run(self.args("list"))
        self.assertFalse(any("contents/" in path for path, _ in self.gh.calls))

    def test_account_change_requires_rebinding(self):
        (self.root / "binding.json").write_text(json.dumps({"account": "someone-else", "repository": "example/personal-resources"}))
        with self.assertRaises(r.ResourceError):
            r.run(self.args("status"))

    def test_bind_stores_no_credentials(self):
        r.run(self.args("bind", repository="example/personal-resources"))
        self.assertEqual(json.loads((self.root / "binding.json").read_text()),
                         {"account": "example", "repository": "example/personal-resources"})

    def test_export_literal_and_permission_without_overwrite(self):
        mapping = self.root / "map.json"
        mapping.write_text(json.dumps({"API_KEY": "secrets.api_key", "MODEL": "config.default_model"}))
        output = self.root / ".env.resources"
        args = self.args("export", id="example-dev", map_file=str(mapping), output=str(output), overwrite=False)
        result = r.run(args)
        self.assertIn("API_KEY='test-only-private-value'", output.read_text())
        self.assertNotIn("test-only-private-value", json.dumps(result))
        if os.name != "nt":
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(r.ResourceError):
            r.run(args)

    def test_symlink_output_rejected(self):
        target = self.root / "original"
        target.write_text("preserve")
        link = self.root / "link"
        link.symlink_to(target)
        with self.assertRaises(r.ResourceError):
            r.write_private(link, b"new", overwrite=True)
        self.assertEqual(target.read_text(), "preserve")

    def test_dotenv_dollar_is_literal_and_ambiguous_values_rejected(self):
        item = resource()
        item["secrets"]["api_key"] = "$(do-not-execute)$value#value"
        self.assertEqual(r.env_bytes(item, {"KEY": "secrets.api_key"}), b"KEY='$(do-not-execute)$value#value'\n")
        for value in ("a'b", "a\nb", "a\x00b"):
            item["secrets"]["api_key"] = value
            with self.assertRaises(r.ResourceError):
                r.env_bytes(item, {"KEY": "secrets.api_key"})

    def test_secret_fields_and_credential_urls_rejected_in_config(self):
        for config in ({"api_key": "value"}, {"base_url": "postgres://user:pass@localhost/db"},
                       {"base_url": "https://example.com?token=private"}):
            item = resource()
            item["config"] = config
            with self.assertRaises(ValueError):
                r.validate_resource(item)

    def test_existing_record_requires_current_sha(self):
        path = self.root / "resource.json"
        path.write_text(json.dumps(resource()))
        with self.assertRaises(r.ResourceError):
            r.run(self.args("put", file=str(path), expected_sha=None))
        self.assertFalse(any(method == "PUT" for _, method in self.gh.calls))

    def test_successful_update_verified_and_unrelated_records_preserved(self):
        extra = resource()
        extra["id"] = "unrelated"
        self.gh.data["resources"].append(extra)
        item = resource()
        item["config"]["default_model"] = "new-model"
        path = self.root / "resource.json"
        path.write_text(json.dumps(item))
        result = r.run(self.args("put", file=str(path), expected_sha="sha-one"))
        self.assertTrue(result["verified"])
        self.assertEqual(self.gh.data["resources"][1], extra)
        self.assertNotIn("test-only-private-value", json.dumps(result))

    def test_new_record_and_duplicate_ids(self):
        item = resource()
        item["id"] = "another"
        path = self.root / "resource.json"
        path.write_text(json.dumps(item))
        r.run(self.args("put", file=str(path), expected_sha=None))
        self.assertEqual(len(self.gh.data["resources"]), 2)
        with self.assertRaises(ValueError):
            r.validate_catalog({"version": 1, "resources": [item, copy.deepcopy(item)]})

    def test_gh_failure_does_not_echo_stderr(self):
        with patch.object(r.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "", "test-only-private-value")):
            with self.assertRaises(r.ResourceError) as exc:
                REAL_API("user")
        self.assertNotIn("test-only-private-value", str(exc.exception))

    def test_resource_only_install_does_not_touch_notes_or_mcp(self):
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        gh = bin_dir / "gh"
        gh.write_text("#!/bin/sh\nexit 99\n")
        gh.chmod(0o755)
        skills = self.root / "installed"
        notes = skills / "github-notes"
        notes.mkdir(parents=True)
        (notes / "keep").write_text("preserve")
        result = subprocess.run([sys.executable, str(ROOT / "install.py"), "--skill", "github-resources", "--skip-mcp", "--skills-dir", str(skills)],
                                env=dict(os.environ, PATH=str(bin_dir)), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)["mcp_registered"])
        self.assertTrue((skills / "github-resources/SKILL.md").exists())
        self.assertEqual((notes / "keep").read_text(), "preserve")


if __name__ == "__main__":
    unittest.main()
