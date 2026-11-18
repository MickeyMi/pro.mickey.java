#!/usr/bin/env python3
"""Resolve a release and immutable upstream index; emit Actions outputs."""
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

UPSTREAM = "ghcr.io/fatedier/frps"
REQUIRED = {("linux", "amd64"), ("linux", "arm64")}


def normalize_version(value):
    value = value.strip()
    if not re.fullmatch(r"v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", value):
        raise ValueError("版本必须是稳定版，例如 v0.72.0 或 0.72.0")
    return "v" + value.removeprefix("v")


def github_release(path):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "frps-custom"}
    if os.environ.get("GH_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
    request = urllib.request.Request(
        "https://api.github.com/repos/fatedier/frp/releases/" + path, headers=headers
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                release = json.load(response)
            if release.get("draft") or release.get("prerelease"):
                raise ValueError("仅支持已发布的稳定 release")
            normalize_version(release["tag_name"])
            return release
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def inspect_image(reference, optional=False):
    result = subprocess.run(
        ["docker", "buildx", "imagetools", "inspect", reference,
         "--format", "{{json .Manifest}}"],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode:
        # Only a genuine missing tag is a cache miss. Auth/network failures
        # must fail visibly instead of silently causing a publication.
        error = result.stderr.lower()
        if optional and ("manifest unknown" in error or "not found" in error):
            return None
        raise RuntimeError(f"无法检查镜像 {reference}: {result.stderr.strip()}")
    return json.loads(result.stdout)


def check_platforms(manifest):
    found = {
        (entry.get("platform", {}).get("os"), entry.get("platform", {}).get("architecture"))
        for entry in manifest.get("manifests", [])
    }
    if not REQUIRED.issubset(found):
        raise ValueError("镜像缺少 linux/amd64 或 linux/arm64；等待上游镜像发布完成后重试")


def manifest_digest(manifest):
    digest = manifest.get("digest", "")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise ValueError("镜像摘要无效")
    return digest


def already_published(version_manifest, latest_manifest):
    if not version_manifest or not latest_manifest:
        return False
    try:
        check_platforms(version_manifest)
        check_platforms(latest_manifest)
        return manifest_digest(version_manifest) == manifest_digest(latest_manifest)
    except ValueError:
        return False


def resolve(requested, event, repository):
    latest = normalize_version(github_release("latest")["tag_name"])
    version = normalize_version(requested) if requested.strip() else latest
    if version != latest:
        actual = normalize_version(github_release("tags/" + version)["tag_name"])
        if actual != version:
            raise ValueError("上游 release 与请求版本不一致")
    repository = repository.lower()
    if not re.fullmatch(r"[a-z0-9_.-]+/[a-z0-9_.-]+", repository):
        raise ValueError("GITHUB_REPOSITORY 必须是 owner/repo")
    image = "ghcr.io/" + repository
    source = inspect_image(UPSTREAM + ":" + version)
    check_platforms(source)
    base = UPSTREAM + "@" + manifest_digest(source)
    build = True
    if event == "schedule":
        build = not already_published(
            inspect_image(image + ":" + version, optional=True),
            inspect_image(image + ":latest", optional=True),
        )
    tags = [image + ":" + version, image + ":" + version[1:]]
    if version == latest:
        tags.append(image + ":latest")
    return {"version": version, "base": base, "image": image,
            "tags": ",".join(tags), "build": str(build).lower()}


def main():
    values = resolve(os.environ.get("REQUESTED_VERSION", ""),
                     os.environ.get("GITHUB_EVENT_NAME", "workflow_dispatch"),
                     os.environ["GITHUB_REPOSITORY"])
    for key, value in values.items():
        print(f"{key}={value}")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            for key, value in values.items():
                output.write(f"{key}={value}\n")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
