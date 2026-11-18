# frps-custom

基于官方 `ghcr.io/fatedier/frps` 镜像，将 `/usr/bin/frps` 重命名为
`/usr/bin/java`，并直接作为容器 PID 1 启动。发布 `linux/amd64` 和
`linux/arm64` 两种架构。

本仓库的镜像地址：**`ghcr.io/mickeymi/pro.mickey.java`**。
工作流根据 GitHub 仓库名称自动生成地址；迁移仓库无需修改工作流。

## 推送和发布

当前本地项目已关联 `git@github.com:MickeyMi/pro.mickey.java.git`，
使用 `main` 分支，并已准备首次提交。在项目目录执行：

```sh
git push
```

SSH 必须登录到拥有此仓库写权限的 GitHub 账户。可使用 `ssh -T git@github.com`
检查当前身份；如果推送提示 `Permission denied to ...`，需要切换到正确账户的 SSH 密钥。

默认分支的 push 会自动查询上游最新稳定 release，进行两种架构的运行验证，
然后发布到 GHCR。使用 GitHub 自动提供的 `GITHUB_TOKEN`，无需配置 PAT
或 Docker Hub 密码。发布结果和镜像摘要可在 Actions 运行摘要中查看。

首次使用需要仓库允许 GitHub Actions 和 `packages: write`。
工作流已声明所需权限；组织策略仍可能限制发布。GHCR 新包默认可能为私有，
如需匿名拉取，在 Package settings 中将其可见性设为 Public。
已存在的同名包需要允许本仓库的 Actions 访问。

## 上游更新与手动版本

| 触发方式 | 行为 |
| --- | --- |
| 默认分支 push | 构建最新稳定版，即使该版本已发布也重新构建，以应用项目修改 |
| 每小时第 17 分钟 | 查询上游最新稳定 release；版本标签与 `latest` 已一致且包含两种架构时跳过 |
| Actions → Build and publish frps-custom → Run workflow | 留空构建最新稳定版；也可输入 `v0.72.0` 或 `0.72.0` |
| PR / 非默认分支 push | 构建、测试，不发布镜像 |

手动发布时选择默认分支。仅接受正式稳定版，不接受 `latest` 字符串、预发布版本或任意镜像地址。
上游仓库的 release 事件无法直接触发本仓库工作流，因此采用定时查询，通常下一次检查时跟进，
不是实时 webhook。GitHub 定时任务可能延迟；长期无活动的公共仓库可能在 60 天后被停用定时任务，
届时需要在 Actions 中重新启用。

若上游 release 已创建，但 GHCR 镜像或任一架构还未发布完成，本次任务会失败，
不发布自定义版本；下一次定时检查会重新尝试。网络或鉴权错误也会显式失败。
此流程只更新镜像仓库，不会自动重启你的服务器容器。

例如发布 `v0.72.0` 时生成：

```text
ghcr.io/mickeymi/pro.mickey.java:v0.72.0
ghcr.io/mickeymi/pro.mickey.java:0.72.0
ghcr.io/mickeymi/pro.mickey.java:latest
```

仅当所选版本等于检查时的上游最新稳定版时才更新 `latest`。
手动构建旧版不会回退 `latest`。版本标签允许重新构建覆盖；需要完全固定时使用镜像摘要。
Actions 在开始时固定上游多架构摘要，确保同一次测试和发布使用相同的上游镜像。

## 运行

复制配置并设置自己的认证 token：

```sh
cp config/frps.example.toml config/frps.toml
# 编辑 config/frps.toml，将 auth.token 替换为长随机字符串，并同步到 frpc。
docker pull ghcr.io/mickeymi/pro.mickey.java:latest
docker run -d \
  --name frps-custom \
  --restart unless-stopped \
  -p 7000:7000 \
  --mount "type=bind,src=$(pwd)/config/frps.toml,dst=/etc/frp/frps.toml,readonly" \
  ghcr.io/mickeymi/pro.mickey.java:latest
```

示例只映射控制端口 7000。根据实际代理配置，另行映射所需 TCP/UDP 端口。
镜像不内置认证 token，也不内置服务配置；运行时必须挂载配置，或者传入自己的 frps 参数。
`config/frps.toml` 被 Git 忽略，避免提交实际认证配置。

```sh
# frps 的命令行参数照常使用。
docker run --rm ghcr.io/mickeymi/pro.mickey.java:latest --version
docker logs frps-custom

# Linux 内核看到的 PID 1 进程名和可执行文件。
docker exec frps-custom cat /proc/1/comm
# java
docker exec frps-custom readlink /proc/1/exe
# /usr/bin/java
docker exec frps-custom sh -c 'tr "\000" " " < /proc/1/cmdline; echo'
# /usr/bin/java -c /etc/frp/frps.toml
```

这里的 `java` 是重命名后的 frps 原生程序，不是 JVM，也不支持 Java 参数或 JAR。
该修改会影响常见进程列表中的名称，但不会改变 frps 的协议、日志、帮助文本、二进制内容或身份特征。
镜像的 source/revision 标签保留真实来源。Docker 容器名由 `--name` 单独决定。

## 本地构建和验证

需要 Docker（含 Buildx）和 Python 3.9+。本地 Dockerfile 默认版本为 `v0.72.0`；
Actions 自动跟随上游，不依赖这个默认值，无需逐版提交 Dockerfile。

```sh
docker build --build-arg FRPS_VERSION=v0.72.0 -t frps-custom:local .
python3 -m unittest discover -s tests -v
python3 scripts/smoke.py frps-custom:local v0.72.0
```

运行验证会检查版本、有效/无效配置、PID 1 的 `comm` / `exe` / 启动参数、
7000 端口监听和 SIGTERM 停止，测试容器使用隔离网络并自动清理。
CI 分别在原生 amd64 和 arm64 runner 上执行验证，二者成功后才允许发布。
发布后再次检查镜像架构和标签摘要。测试不涵盖真实 frpc 代理端到端连接。

需要手动构建多架构镜像时，在已配置好跨架构构建支持的 Docker 环境执行：

```sh
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --build-arg FRPS_VERSION=v0.72.0 \
  -t ghcr.io/mickeymi/pro.mickey.java:v0.72.0 \
  --push .
```

## 文件

```text
Dockerfile                      上游镜像、程序重命名与直接启动
.dockerignore                   构建上下文白名单
.gitignore                      忽略实际配置与临时文件
.github/workflows/publish.yml    定时检测、手动构建、双架构测试与 GHCR 发布
.github/dependabot.yml           检查固定的 GitHub Actions 版本更新
config/frps.example.toml         最小服务配置示例
scripts/resolve.py              稳定版本、镜像摘要与是否重建的判断
scripts/smoke.py                Docker 运行验证
tests/test_resolve.py           发布逻辑回归测试
VALIDATION.md                   创建项目时的本地验证记录
```

## 参考

- [frp 上游项目](https://github.com/fatedier/frp)
- [上游 v0.72.0 Dockerfile](https://github.com/fatedier/frp/blob/v0.72.0/dockerfiles/Dockerfile-for-frps)
- [GitHub Actions 定时触发规则](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
- [使用 Actions 发布镜像](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images)
- [GHCR 权限与可见性](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [Buildx 镜像摘要和架构检查](https://docs.docker.com/reference/cli/docker/buildx/imagetools/inspect/)
