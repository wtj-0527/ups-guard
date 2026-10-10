# 原生 NUT 驱动事件桥接（可选）

标准 NUT 的驱动通过本地 Unix socket 向 upsd 推送变量更新；标准 upsd TCP 协议不提供 `LISTEN`。本功能使用驱动 socket 接收更新，再通过认证接口转发给后端。协议依据：[NUT 2.8.2 driver socket protocol](https://networkupstools.org/historic/v2.8.2/docs/developer-guide.chunked/sock-protocol.html)。

适用于使用本仓库 Docker Compose、由内置 NUT 容器运行单个驱动的部署。在 Compose 使用的 `.env` 中设置：

```dotenv
NUT_EVENT_BRIDGE=true
NUT_EVENT_SECRET=<至少16个字符的随机串，例如 openssl rand -hex 32 的输出>
```

`NUT_EVENT_SECRET` 是桥接专用的共享密钥，NUT 容器不再需要、也不应持有全权限的 `API_TOKEN`；在 Web 界面修改 API Token 也不会影响桥接。未设置或长度不足时桥接不会启动（容器日志会给出警告），事件入口返回 503。重建并启动 `nut-server` 与 `backend`。在界面选择事件驱动或混合模式，并启用事件驱动。默认不启用桥接，外部 NUT 服务及其他部署方式保持现有行为。

桥接只请求一次 `DUMPALL`，随后接收 `SETINFO`、`DATAOK`、`DATASTALE`，以10秒 `PING` 验证驱动连接，并每15秒发送健康心跳。`ups.status` 的连续变化逐条排队。它不会向UPS发送控制命令，不需要把驱动socket暴露到宿主网络。

后端35秒（约两个心跳周期）未收到有效健康快照，或明确收到驱动失效消息时，事件模式失效。如果界面开启自动降级，后端暂时使用常规NUT轮询间隔（默认5秒）查询upsd；有效事件恢复后自动切回。关闭自动降级则报离线。upsd同时不可用或数据过期时不会使用旧快照伪装在线。单个格式错误/过期HTTP帧被拒绝，不刷新心跳。

`/api/system/monitoring-stats` 返回事件来源、累计事件帧数和最近帧年龄（从未收到帧时为 `null`）。事件模式下仅新事件帧计入"今日通信次数"和"最后更新时间"，"响应时间"只统计真实的 NUT 查询。事件健康期间不会执行监控取数的 `LIST VAR`；缓存健康检查、关机倒计时、硬件USB驱动以及用户主动诊断/控制仍可能运行。驱动在硬件层的检测周期决定最终延迟，不保证所有UPS都在500毫秒内发现状态变化。

桥接只自动选择唯一驱动socket。多驱动环境可在NUT容器设置 `NUT_DRIVER_SOCKET` 指定路径；`NUT_EVENT_URL` 可指定内部后端事件入口。默认入口为 `http://backend:8000/api/system/driver-event`，该入口只接受 `X-NUT-Event-Secret` 头鉴权（不接受 API Token），必须由可信内部网络连接；跨主机部署需自行提供安全传输与访问限制。

代码通过Dockerfile进入镜像，重建时保留；备份和迁移须保留源码、Compose、私有环境配置与持久化数据。上游升级仍需迁移本地尚未合并的补丁。
