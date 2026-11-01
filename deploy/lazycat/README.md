# UPS Guard - 懒猫微服部署指南

## 文件说明

| 文件 | 说明 |
|------|------|
| `.env` | 部署配置（Docker Hub 用户名等） |
| `deploy-to-lazycat.ps1` | Windows 部署脚本 |
| `deploy-to-lazycat.sh` | Mac/Linux 部署脚本 |
| `Dockerfile` | Docker 镜像构建配置 |
| `entrypoint.sh` | 容器启动脚本 |
| `lzc-manifest.yml` | 懒猫应用清单 |
| `lzc-build.yml` | LPK 构建配置 |
| `lzc-icon.png` | 应用图标 |

## 快速部署

### Windows (PowerShell)

```powershell
# 1. 配置 .env 文件
#    设置 DOCKERHUB_USERNAME 为你的 Docker Hub 用户名

# 2. 运行部署脚本
.\deploy-to-lazycat.ps1
```

### Mac/Linux (Bash)

```bash
# 1. 配置 .env 文件
#    设置 DOCKERHUB_USERNAME 为你的 Docker Hub 用户名

# 2. 添加执行权限并运行
chmod +x deploy-to-lazycat.sh
./deploy-to-lazycat.sh
```

## 命令行参数

| 参数 | PowerShell | Bash | 说明 |
|------|------------|------|------|
| 详细输出 | `-Verbose` | `-v` | 显示详细构建日志 |
| 自动安装 | `-AutoInstall` | `-a` | 跳过安装确认 |
| 帮助 | `-Help` | `-h` | 显示帮助信息 |

## 部署流程

脚本会自动完成以下步骤：

1. 构建前端
2. 构建 Docker 镜像
3. 推送到 Docker Hub
4. 复制到懒猫 Registry
5. 更新 manifest 中的镜像地址
6. 构建并安装 LPK 包

## 版本管理

版本号从 `lzc-manifest.yml` 中的 `version` 字段自动提取，修改该字段即可更新版本。

## 仅构建和发布 LPK

已有发布使用阿里云 ACR 镜像和 GitHub Release 的 LPK 附件。
如果只需要发布，不要运行包含安装步骤的 `deploy-to-lazycat.sh`。
在项目根目录执行以下步骤（示例为 amd64，与现有发布架构一致）：

```bash
VERSION=1.0.85
SOURCE_COMMIT=$(git rev-parse HEAD)
IMAGE=registry.cn-shanghai.aliyuncs.com/wtjking/ups-guard:${VERSION}

# 构建前需提交源码，并确保 manifest 中的版本和镜像标签与 VERSION 一致
git archive "${SOURCE_COMMIT}" | docker build --platform linux/amd64 \
  --build-arg APP_VERSION="${VERSION}" --build-arg VCS_REF="${SOURCE_COMMIT}" \
  -f deploy/lazycat/Dockerfile -t "${IMAGE}" -
docker push "${IMAGE}"

# 只打包，不安装
mkdir -p deploy/lazycat/content
lzc-cli project build deploy/lazycat
```

验证镜像版本、提交标识及 Mock 模式下的只读接口后，再将生成的
`cloud.lazycat.app.ups-guard-v${VERSION}.lpk` 作为 GitHub Release 附件发布，
并在发布说明中记录源码提交、镜像摘要和 LPK 的 SHA-256。
该流程不执行 `lzc-cli app install`，也不修改任何运行中的 UPS 配置。

### 上游构建源不可用时的补丁镜像

`Dockerfile.patch` 以 v1.0.84 的固定镜像摘要复用运行时依赖，
用于本次依赖清单未变化的补丁发布。使用前必须确认：

```bash
git diff --exit-code v1.0.84 HEAD -- \
  backend/pyproject.toml backend/uv.lock frontend/package.json frontend/package-lock.json
```

构建上下文应只包含已提交的当前源码及当前源码构建出的 `frontend/dist`，
并使用 `-f deploy/lazycat/Dockerfile.patch`，同时传入 `APP_VERSION` 和
`VCS_REF`。依赖清单有变化时应使用完整 Dockerfile 重新构建。
