import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import resolve


def manifest(digit="a", arches=("amd64", "arm64")):
    return {"digest": "sha256:" + digit * 64,
            "manifests": [{"platform": {"os": "linux", "architecture": arch}}
                          for arch in arches]}


class ReleaseTests(unittest.TestCase):
    def test_normalize_and_reject_invalid_input(self):
        self.assertEqual(resolve.normalize_version(" 0.72.0 "), "v0.72.0")
        for value in ["latest", "v0.72", "v0.72.0-rc1", "v01.2.3", "v0.72.0\nx=y", "$(id)", ""]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                resolve.normalize_version(value)

    def test_platforms_ignore_attestations_but_require_both(self):
        data = manifest(arches=("amd64", "arm64", "unknown"))
        resolve.check_platforms(data)
        with self.assertRaises(ValueError):
            resolve.check_platforms(manifest(arches=("amd64",)))

    def test_digest_validation(self):
        with self.assertRaises(ValueError):
            resolve.manifest_digest({"digest": "sha256:bad"})

    @patch.object(resolve, "github_release", return_value={"tag_name": "v0.72.0"})
    @patch.object(resolve, "inspect_image", return_value=manifest())
    def test_push_builds_latest_and_lowercases_image(self, inspect, release):
        result = resolve.resolve("", "push", "SomeOwner/Frps-Custom")
        self.assertEqual(result["image"], "ghcr.io/someowner/frps-custom")
        self.assertEqual(result["version"], "v0.72.0")
        self.assertEqual(result["build"], "true")
        self.assertIn(":latest", result["tags"])
        self.assertEqual(result["base"], resolve.UPSTREAM + "@sha256:" + "a" * 64)

    @patch.object(resolve, "github_release", side_effect=[{"tag_name": "v0.72.0"}, {"tag_name": "v0.71.0"}])
    @patch.object(resolve, "inspect_image", return_value=manifest())
    def test_manual_old_release_never_moves_latest(self, inspect, release):
        result = resolve.resolve("0.71.0", "workflow_dispatch", "owner/repo")
        self.assertNotIn(":latest", result["tags"])
        self.assertEqual(result["build"], "true")
        release.assert_called_with("tags/v0.71.0")

    @patch.object(resolve, "github_release", return_value={"tag_name": "v0.72.0"})
    @patch.object(resolve, "inspect_image", side_effect=[manifest(), manifest("b"), manifest("b")])
    def test_schedule_skips_completed_release(self, inspect, release):
        self.assertEqual(resolve.resolve("", "schedule", "owner/repo")["build"], "false")

    @patch.object(resolve, "github_release", return_value={"tag_name": "v0.72.0"})
    def test_schedule_recovers_missing_or_partial_publication(self, release):
        for version, latest in [(None, None), (manifest(), None),
                                (manifest(), manifest("b")),
                                (manifest(arches=("amd64",)), manifest())]:
            with self.subTest(version=version, latest=latest):
                with patch.object(resolve, "inspect_image", side_effect=[manifest(), version, latest]):
                    self.assertEqual(resolve.resolve("", "schedule", "owner/repo")["build"], "true")

    @patch.object(resolve, "github_release", return_value={"tag_name": "v0.72.0"})
    @patch.object(resolve, "inspect_image", return_value=manifest(arches=("amd64",)))
    def test_incomplete_upstream_fails_before_build(self, inspect, release):
        with self.assertRaises(ValueError):
            resolve.resolve("", "push", "owner/repo")

    @patch.object(resolve.subprocess, "run")
    def test_registry_missing_is_distinct_from_auth_and_network_errors(self, run):
        for message in ["manifest unknown", "not found"]:
            run.return_value = subprocess.CompletedProcess([], 1, "", message)
            self.assertIsNone(resolve.inspect_image("example:tag", optional=True))
        for message in ["unauthorized", "denied", "TLS handshake timeout"]:
            run.return_value = subprocess.CompletedProcess([], 1, "", message)
            with self.assertRaises(RuntimeError):
                resolve.inspect_image("example:tag", optional=True)

    @patch.object(resolve.subprocess, "run")
    def test_inspect_uses_structured_docker_arguments(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, json.dumps(manifest()), "")
        self.assertEqual(resolve.inspect_image("example:tag"), manifest())
        self.assertEqual(run.call_args.args[0][4], "example:tag")


if __name__ == "__main__":
    unittest.main()
