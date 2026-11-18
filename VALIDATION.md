# 本地验证记录

验证日期：2026-11-19（Asia/Shanghai）。

## 已完成

- Python 单元测试：10 项通过，覆盖输入校验、手动旧版不更新 latest、定时跳过、
  缺失/不完整发布的恢复、上游架构缺失、摘要校验、仓库名称小写化以及鉴权/网络错误处理。
- `scripts/resolve.py` 和 `scripts/smoke.py` 的 Python 语法编译通过。
- 使用官方 actionlint v1.7.12 检查工作流通过；下载时校验官方 SHA-256 校验清单。
  本次未运行 shellcheck 或 pyflakes。
- 工作流和 Dependabot 配置的 YAML 解析通过。
- Actions 引用已固定到通过 GitHub API 核实的提交 SHA。
- 实际查询 GitHub Releases：当前上游最新稳定版为 `v0.72.0`。
- 实际查询官方 GHCR：`v0.72.0` 提供 `linux/amd64` 和 `linux/arm64`。
  查询时上游索引摘要为
  `sha256:17abb20dd392557a44070d9726954630c0eb1f7a9bd6ead5ae9150d165179ea4`。
- 检查目标 GitHub 仓库时没有已有分支或提交。
- 已设置用户指定的 SSH 远端并预检推送。当前 SSH 身份没有目标仓库写权限；
  需要切换到有权限的 GitHub 账户后推送，远端尚未改动。

## 尚未执行

创建项目的本机没有 Docker，因此尚未实际构建或启动镜像，也未推送到 GitHub 或发布 GHCR。
此记录不代表容器运行验证已经通过。

首次 push 后，GitHub Actions 会在原生 amd64 / arm64 runner 上分别运行：

1. 构建指定摘要的上游镜像。
2. 检查程序版本和有效/无效配置。
3. 验证 PID 1 的进程名为 `java`、可执行文件为 `/usr/bin/java`，且启动参数正确。
4. 检查服务监听及 SIGTERM 停止。
5. 两种架构均成功后发布 GHCR，并检查最终架构清单和标签摘要。

具体容器验证和发布结果以 GitHub Actions 的首次运行结果为准。
