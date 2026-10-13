# 发布与下载

公开安装包应从 [GitHub Releases](https://github.com/Livia-Tassel/PaperVault/releases) 下载。版本变更见 [CHANGELOG](../CHANGELOG.md)，自行构建见 [README 的 Windows 步骤](../README.md#windows-自行打包)和[完整构建指南](WINDOWS.md)。

## 当前状态

截至 2026-10-13，0.2.2 有本机 Windows 构建与安装验收记录，但没有公开的 GitHub Release 安装包。macOS / Linux 安装包尚未验证。

首次 [Windows CI](https://github.com/Livia-Tassel/PaperVault/actions/runs/38252193665)（2026-10-12）在冻结后台退出检查中失败：关闭标准输入后，进程未在 15 秒内退出，触发 `subprocess.TimeoutExpired`。该次未执行 NSIS 构建，只上传测试报告。后续执行请查看 [Actions 最新状态](https://github.com/Livia-Tassel/PaperVault/actions/workflows/windows.yml)。

## 安装包在哪里

| 位置 | 用途 |
| --- | --- |
| `apps/desktop/src-tauri/target/.../bundle/nsis/` | 自行构建成功后生成的本地安装器；`target/` 被 Git 忽略 |
| Actions 的 `PaperVault-Windows-x64` 附件 | Windows 流程全部通过后上传的 CI 产物；以实际运行附件为准 |
| GitHub Releases | 对外发布和长期下载入口；现有流程尚未自动创建 Release |
| `docs/verification/` | 小型测试证据、日志和哈希清单，不能替代安装器 |

因此，GitHub 的 `blob/main/.../target/...exe` 源码链接不会提供本机安装包。演示 MP4 同样保存在 Git 忽略的 `artifacts/` 中，仓库仅归档字幕、署名与验证记录。

## 校验本机 0.2.2 安装器

[0.2.2 交付清单](verification/0.2.2/release-manifest.json)记录的历史本机文件为 536,386,869 字节，SHA-256：

```text
b883a2e3822b2e81ff902214595575c25a026784df09aa068aeaf848a8a89708
```

可以在 Windows 中计算文件哈希：

```powershell
Get-FileHash -Algorithm SHA256 .\apps\desktop\src-tauri\target\x86_64-pc-windows-msvc\release\bundle\nsis\PaperVault_0.2.2_x64-setup.exe
```

这个哈希只标识当时验证的文件；自行重建、不同 WebView2 打包模式或依赖环境可能产生不同字节，不应冒用旧清单。
