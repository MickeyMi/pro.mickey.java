# pro.mickey.java

进程名：`java`。镜像：`ghcr.io/mickeymi/pro.mickey.java`。

推送到 `main` 自动构建发布；每小时检查更新。
手动运行：Actions → Publish → Run workflow，版本留空使用最新版，也可填 `v0.72.0`。
支持 `linux/amd64` 和 `linux/arm64`。手动构建旧版不会覆盖 `latest`。

复制 `config/config.example.toml` 为 `config/config.toml`，修改 token 后运行：

```sh
docker run -d --name java --restart unless-stopped \
  -p 7000:7000 \
  -v "$(pwd)/config/config.toml:/etc/java/config.toml:ro" \
  ghcr.io/mickeymi/pro.mickey.java:latest
```

需要其他代理端口时自行添加端口映射。已有容器升级时，将配置挂载位置改为 `/etc/java/config.toml`。
如镜像为私有，需要登录 GHCR，或将包设为公开。

最终镜像从 Alpine 重新组装，只复制重命名后的程序；不继承上游镜像层，也不添加自定义标签。
文件名、启动路径和配置路径使用 `java`；程序内部的 `frp` 字符串、日志和协议保持原样，无法保证镜像内容完全不包含该词。

构建时在两种架构上执行 `java --version` 进行基本验证。本机未安装 Docker，容器构建以 Actions 结果为准。
