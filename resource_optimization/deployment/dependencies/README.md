# 外部依赖身份

## 模型

固定来源为 `meta-llama/Llama-3.1-8B-Instruct` 的 revision `07eb05b21d191a58c577b4a45982fe0c049d0693`，适用 Meta Llama 3.1 授权及该模型的访问条件。[官方固定版本](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct/tree/07eb05b21d191a58c577b4a45982fe0c049d0693)，[官方版本文件身份 API](https://huggingface.co/api/models/meta-llama/Llama-3.1-8B-Instruct/revision/07eb05b21d191a58c577b4a45982fe0c049d0693?blobs=true)。

[model.json](model.json) 列出九个 checkpoint 聚合输入的文件名、大小、SHA256，以及另行需要的 `generation_config.json`。四个 safetensors shard、config、index 和三个 tokenizer 文件形成严格 checkpoint 身份 `8a09c60f3256779c16925f8209c9399ba4a1ee0406caf65bd2637ffd99287d6d`。原文件全字节重新哈希通过，官方固定 revision 的 Git blob/LFS 内容身份与这些文件逐项一致，generation EOS 也匹配。

记录中的等内容下载来源为 `NousResearch/Meta-Llama-3.1-8B-Instruct@d10aef7999a2b5ba950ab3974312feeedbfe0b77`。其六个控制文件已从该固定 revision 读取并逐字节核对，四个权重 LFS SHA256 与原 checkpoint 一致。当前官方 main 的 `tokenizer_config.json` 为 55351 B，已测文件为 50870 B，获取时使用上述固定 revision。

## PowerTool 与适配器

官方页面提供 Digital Power Tool Software **2.32.27**，适配器型号为 **MAXPOWERTOOL002#**。适配器通过 USB Type-A 到 Mini-B 连接主机，通过 16-pin ribbon 连接 PMBus。[官方产品及软件入口](https://www.analog.com/en/resources/evaluation-hardware-and-software/evaluation-boards-kits/maxpowertool002.html)，[官方 2.32.27 下载页面](https://www.analog.com/en/resources/evaluation-hardware-and-software/embedded-development-software/software-download.html?swpart=SD_XRKA6ZW)，[官方硬件快速指南](https://www.analog.com/media/en/technical-documentation/user-guides/powertool-maxpowertool002-quick-start-guide.pdf)。

[powertool.json](powertool.json) 保存现场安装器、runtime、DLL/XML 和适配器驱动的身份。现场安装器为 10609584 B，SHA256 `0690b310c2288d577f38f35bed865fecddef5a6e93546305381fb2e9b86d20cf`，Authenticode 校验为 Valid，签发主体为 Analog Devices International UC。本次直接重新下载请求超时，`same_hash_retrieved_during_audit=false` 单独保留。

现场安装目录为 `C:/Program Files (x86)/Maxim Integrated Products/MaximDigitalPower`。所需官方 `MaximDigitalPower.exe` 为 7859200 B，SHA256 `d5749e5ebb80b4ad7c81c73cc9863467bb988915922a9337da75bb304fc23f31`。遥测准备及采样使用 32-bit Windows PowerShell、.NET Framework 4/WPF 和兼容的 FTDI D2XX 驱动。现场 Digital Power Controller 的驱动版本为 2.12.10.0，32-bit native D2XX 文件版本为 3.02.10，具体身份均作为 observed 数据记录。

从用户已取得的厂商安装目录运行 `tools/power/prepare_powertool.ps1`，在新外部目录生成与公开 `powertool_runtime_manifest.json` 对应的 runtime。公开仓库保存准备器、身份与测量代码，厂商安装材料由使用者按其条款取得。

## Windows XDMA

驱动固定第三方镜像、两阶段 patch、规范化及已测源码 SHA 见 [驱动准备说明](../../../deploy/driver/README.md) 和 [public_source_manifest.json](../../../deploy/driver/public_source_manifest.json)。该路径的 17 个 C/H 与 4 个构建输入内容闭包已核对。AMD 官方 archive 身份保持 UNVERIFIED，新主机的编译、签名和加载资格由部署验证建立。
