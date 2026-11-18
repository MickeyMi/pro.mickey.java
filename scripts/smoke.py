#!/usr/bin/env python3
"""Run against a locally built image on its native architecture."""
import argparse
import json
from pathlib import Path
import secrets
import subprocess
import tempfile
import time
import uuid


def docker(*args, check=True):
    return subprocess.run(["docker", *args], check=check, capture_output=True,
                          text=True, timeout=90)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def smoke(image, version):
    info = json.loads(docker("image", "inspect", image).stdout)[0]
    require(info["Config"]["Entrypoint"] == ["/usr/bin/java"], "ENTRYPOINT 不正确")
    actual = docker("run", "--rm", "--network", "none", image, "--version").stdout.strip()
    require(actual.removeprefix("v") == version.removeprefix("v"), f"版本不匹配: {actual}")
    name = "frps-smoke-" + uuid.uuid4().hex[:12]
    with tempfile.TemporaryDirectory(prefix="frps-smoke-") as directory:
        config = Path(directory) / "frps.toml"
        config.write_text('bindAddr = "127.0.0.1"\nbindPort = 7000\n'
                          'auth.method = "token"\nauth.token = "' + secrets.token_hex(24) + '"\n',
                          encoding="utf-8")
        mount = f"type=bind,src={config},dst=/etc/frp/frps.toml,readonly"
        docker("run", "--rm", "--network", "none", "--mount", mount,
               image, "verify", "-c", "/etc/frp/frps.toml")
        try:
            docker("run", "-d", "--name", name, "--network", "none", "--mount", mount, image)
            listening = False
            for _ in range(30):
                state = docker("inspect", "--format", "{{.State.Running}}", name).stdout.strip()
                require(state == "true", "服务在启动时退出")
                proc = docker("exec", name, "cat", "/proc/net/tcp").stdout
                listening = any(len(fields := line.split()) > 3
                                and fields[1].endswith(":1B58") and fields[3] == "0A"
                                for line in proc.splitlines()[1:])
                if listening:
                    break
                time.sleep(1)
            require(listening, "7000 端口未在 30 秒内监听")
            require(docker("exec", name, "cat", "/proc/1/comm").stdout.strip() == "java",
                    "PID 1 comm 不是 java")
            require(docker("exec", name, "readlink", "/proc/1/exe").stdout.strip() == "/usr/bin/java",
                    "PID 1 可执行文件路径不正确")
            argv = docker("exec", name, "cat", "/proc/1/cmdline").stdout.split("\0")
            require(argv[:3] == ["/usr/bin/java", "-c", "/etc/frp/frps.toml"], "参数传递不正确")
            docker("stop", "--time", "10", name)
            state = json.loads(docker("inspect", name).stdout)[0]["State"]
            require(not state["Running"] and state["ExitCode"] in (0, 143),
                    f"SIGTERM 停止异常: {state['ExitCode']}")
        except Exception:
            print(docker("logs", name, check=False).stdout)
            raise
        finally:
            docker("rm", "-f", name, check=False)
        config.write_text("not valid = [", encoding="utf-8")
        invalid = docker("run", "--rm", "--network", "none", "--mount", mount,
                         image, "verify", "-c", "/etc/frp/frps.toml", check=False)
        require(invalid.returncode != 0, "无效配置未被拒绝")
    print(f"PASS: {image}: version, config, PID 1 java, argv, listener, SIGTERM")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("image")
    parser.add_argument("version")
    args = parser.parse_args()
    smoke(args.image, args.version)
