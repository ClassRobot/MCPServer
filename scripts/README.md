# Deployment Scripts

这个目录放项目级辅助脚本，主要用于把 Docker 构建、容器启动和基础验证收束成更稳定的一键入口。

## 当前脚本

- `deploy-docker.ps1`: Windows PowerShell 一键构建并启动生产容器。
- `deploy-docker.sh`: Linux/macOS shell 一键构建并启动生产容器。

## Docker 构建参数

默认使用 Debian 官方 apt 源。若部署网络需要镜像源，可通过脚本参数或环境变量显式传入：

- PowerShell: `-AptDebianMirror` 与 `-AptDebianSecurityMirror`
- Shell: `APT_DEBIAN_MIRROR` 与 `APT_DEBIAN_SECURITY_MIRROR`

## 使用原则

- 脚本只编排项目已有的 Dockerfile 和环境变量，不隐藏新的运行逻辑。
- 参数默认值必须和 `docs/docker.md` 保持一致。
- 新增脚本时同步补充 README 和 Docker 文档。
