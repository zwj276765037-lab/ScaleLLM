# Windows XDMA polling 驱动依赖

本目录只发布本项目的最小修复 patch、观察到的基线 SHA 和源准备器；**不发布 AMD/Xilinx 全量驱动源码、SYS/CAT、证书或私钥**。原源码包含 Xilinx 专有声明，使用者必须自行从 AMD 获得相应材料和许可。

## 上游来源与可复现缺口

AMD [XAPP1338](https://docs.amd.com/r/en-US/xapp1338-fast-partial-reconfiguration-pci-express/Connect-to-PCIe-Host-and-Partially-Reconfigure-the-FPGA) 指向 [AR65444](https://adaptivesupport.amd.com/s/article/65444?language=en_US) 获取 Windows/Linux XDMA reference driver。现场源带 Xilinx 2019 copyright/revision；相邻原 SYS 与安装原包逐字节相同。

**尚未建立该现场源对应的官方下载 archive SHA 或公共 Git commit。** 包名 `xdma_driver_win_2020_5` 只是现场标签，不能代替官方下载身份。公共 dma_ip_drivers 仓库的 Linux XDMA 不能直接当 Windows 源。本目录记录的是 20 个观察到的 C/H 文件及 4 个构建输入的 SHA，不声称它们都是 AMD 原始未改文件。另有原 `POLL_MODE=1` 适配已显式列出。

如果重新下载的材料与 `observed_base_hashes.json` 不匹配，准备器会 fail closed；须审查具体源差异再移植补丁，不可盲目应用或把未知源码当经过测试的版本。这是当前从零部署仍存在的人工依赖，不是一键完整复现承诺。

## 准备一个独立源码副本

```powershell
python deploy\driver\prepare_source.py inspect --source 'E:\AMD-source\xdma'
python deploy\driver\prepare_source.py prepare --source 'E:\AMD-source\xdma' --output 'E:\build\xdma-gu-polling'
```

输入目录必须含 `libxdma/`、`sys/`、`inc/`。脚本不改输入，不安装/下载/签名；只复制已核源/构建输入并应用精确上下文 patch。允许 CRLF→LF；对于原 INX 唯一 `POLL_MODE` 行，只在副本将 0→1 并核基线。标准接口 GUID `74c7e4a9-6d5d-4a70-bc0d-20691dff9e9d` 与 DEV9018 已存在于观察基线，不需要本地私有 GUID。

最小修复：编译开关默认 off；开关 on 且实际 PCI ID 为 `10EE:9018` 时，在任何 IRQ enable 前固定 per-device allowed mask `0xFFFFFFFE`。所有 5 个 user IRQ W1S 路径、shared/MSI-X ISR/DPC、公开 enable API 统一遵守，禁用 user0 的 API 明确返回不支持；其他 user bit、非9018和默认构建保持行为。DMA IRQ/engine/power policy/应用 ABI 不改。INX 仅匹配 9018，候选版本 `11.38.8.506`，DMA `POLL_MODE=1`。

这是为当前以轮询 DONE/error 的应用准备的包，event0 通知不可用；应用仍必须轮询 error/reset_required。不能仅在运行时写 mask 当永久修复，DPC/enable 生命周期可能恢复它。

## 已验证的编译设置

Windows x64，VS2019 Build Tools / MSBuild 16.11.2，**MSVC 14.29.30037**，WDK/SDK **10.0.19041.0**，KMDF1.15，Win10_Release，保持原 `/Qspectre` 和相应 Spectre 库。其他已装 toolset 缺 Spectre 库曾导致构建失败，不能静默关闭缓解后宣称原设置相同。

在已配置 WDK 的 Developer PowerShell 中：

```powershell
msbuild 'E:\build\xdma-gu-polling\sys\XDMA_Driver.vcxproj' /t:Rebuild /m:2 /nr:false `
  /p:Configuration=Win10_Release /p:Platform=x64 `
  /p:WindowsTargetPlatformVersion=10.0.19041.0 /p:VCToolsVersion=14.29.30037 `
  /p:ScaleLlmGuPolling9018=1 /p:SignMode=Off /p:EnableTestSign=false `
  /p:GenerateTestCertificate=false /p:EnableInf2Cat=false /p:MultiProcessorCompilation=false
```

此命令只编译。实际原 candidate 的 on/off 构建均 native0；13 个真实 C 回调事件序列、3 策略模式及两个 mutation 检查通过。已测 SYS SHA 为 `bfc1039ae17cbac465a268a96922d60ebd702dfe2388df8b66d51b2a60fb0932`（33280 B）；编译器时间戳/打包等可令重建字节不同，不以此 SHA 要求别人伪造相同签名包。

## 新 catalog、自有签名与安装

使用 WDK 的 Inf2Cat 对**本次新 INF/SYS** 建 catalog，在已经合法配置的签名环境使用自己的证书签 CAT；不能复制旧 CAT 覆盖新 SYS。具体工具路径与输出目录由自己的 WDK 安装和构建日志确定，例如：

```powershell
Inf2Cat.exe /driver:'E:\build\candidate-package' /os:10_X64
signtool.exe sign /fd SHA256 /sha1 YOUR_OWN_SIGNING_CERT_THUMBPRINT 'E:\build\candidate-package\XDMA.cat'
signtool.exe verify /v /pa 'E:\build\candidate-package\XDMA.cat'
signtool.exe verify /v /pa /c 'E:\build\candidate-package\XDMA.cat' 'E:\build\candidate-package\XDMA.sys'
signtool.exe verify /v /pa /c 'E:\build\candidate-package\XDMA.cat' 'E:\build\candidate-package\XDMA.inf'
```

这是 Microsoft [测试签名 catalog 的校验口径](https://learn.microsoft.com/en-us/windows-hardware/drivers/install/verifying-the-signature-of-a-test-signed-catalog-file)。实际现场使用既有测试证书与既有测试签名启动状态，`/pa` 及精确 SYS/INF 成员验证成功；`/kp` Microsoft production-root 链校验失败，保留该事实，不能宣称 WHQL/生产内核签名。实际加载资格还取决于本机策略。脚本不创建/导入证书、不改 Secure Boot/testsigning/integrity 或启动状态；自行完成适用的合法签名/加载准备。

安装前保存精确设备 instance、旧 published INF、驱动版本、SYS SHA；用 `pnputil /export-driver oemNN.inf E:\backup\xdma` 导出自己的原包，核 INF/CAT/SYS 完整。确认 XDMA 同名 service 和原 INF 没有绑定其他设备；本专用包只用于唯一9018。关闭所有应用句柄后，管理员可显式安装自己的已签名包：

```powershell
pnputil /add-driver 'E:\build\candidate-package\XDMA.inf' /install
```

记录 native exit；若需重启/返回3010或出现错误，停止，不自动重启或强制继续。核新的 published INF 内容 SHA、SYS SHA、版本、唯一实例/PnP，然后先 `preflight --device`，再 layer0 pilot，最后 full。控制面 user-enable/request/pending 应为0，MSI模式1；当前 DMA POLL_MODE1 下打开 DMA 节点后 channel-enable 为0合法，不能误要求它始终为3。

## 回退

`pnputil /add-driver old.inf /install` **不会保证降级**到较旧版本。准备原包、精确实例及 candidate published INF，保留以下选择：设备管理器对精确实例“更新驱动→浏览→从磁盘安装”选回原 INF；或在确认 candidate 仅绑定该唯一实例且与系统其他设备无共享后，显式卸载**该 candidate published INF**，再扫描并安装原包。不要删除原包、不要使用 `/force`、不要扩大到 PCI bridge/总线。

回退后核实原 SYS SHA/PnP/版本及绑定 INF；失败或要求重启则停下来人工处理。本发布没有自动安装/回退工具，避免把某台机器的 oem 编号、证书或权限状态带到新主机。
