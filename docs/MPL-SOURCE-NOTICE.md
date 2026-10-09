# MPL 组件源码与第三方许可来源

PaperVault 未对下列组件的上游源码作修改。精确版本源码随安装包文档保存在 `third-party-sources/`；公开下载地址同时列于下表。源码沿用各自 MPL-2.0 许可，项目自身许可证不替代这些条款。

Rust `.crate` 归档直接复制自本机官方 Cargo registry 缓存；SHA-256 与 Cargo.lock 校验和逐项一致，并已逐文件核对安装源码与归档内容相同。Lightning CSS 使用 npm 发布版本所记录的官方仓库修订；保存的是完整上游源码归档，未修改归档内容。

| 组件 | 版本 | 随附源码 | 官方源码获取地址 |
| --- | --- | --- | --- |
| selectors | 0.38.0 | [selectors-0.38.0.crate](third-party-sources/selectors-0.38.0.crate) | [官方版本源码](https://static.crates.io/crates/selectors/selectors-0.38.0.crate) |
| lightningcss | 1.32.0 | [lightningcss-1.32.0.tar.gz](third-party-sources/lightningcss-1.32.0.tar.gz) | [官方版本源码](https://codeload.github.com/parcel-bundler/lightningcss/tar.gz/7f8a861bdee476fe90c89a8badeb3fd33a99c51a) |
| lightningcss-win32-x64-msvc | 1.32.0 | [lightningcss-1.32.0.tar.gz](third-party-sources/lightningcss-1.32.0.tar.gz) | [官方版本源码](https://codeload.github.com/parcel-bundler/lightningcss/tar.gz/7f8a861bdee476fe90c89a8badeb3fd33a99c51a) |
| lightningcss | 1.33.0 | [lightningcss-1.33.0.tar.gz](third-party-sources/lightningcss-1.33.0.tar.gz) | [官方版本源码](https://codeload.github.com/parcel-bundler/lightningcss/tar.gz/1d680fa14e9a089c92dc0929f869d6757ae91c30) |
| lightningcss-win32-x64-msvc | 1.33.0 | [lightningcss-1.33.0.tar.gz](third-party-sources/lightningcss-1.33.0.tar.gz) | [官方版本源码](https://codeload.github.com/parcel-bundler/lightningcss/tar.gz/1d680fa14e9a089c92dc0929f869d6757ae91c30) |
| cssparser | 0.37.0 | [cssparser-0.37.0.crate](third-party-sources/cssparser-0.37.0.crate) | [官方版本源码](https://static.crates.io/crates/cssparser/cssparser-0.37.0.crate) |
| cssparser-macros | 0.7.1 | [cssparser-macros-0.7.1.crate](third-party-sources/cssparser-macros-0.7.1.crate) | [官方版本源码](https://static.crates.io/crates/cssparser-macros/cssparser-macros-0.7.1.crate) |
| dtoa-short | 0.3.5 | [dtoa-short-0.3.5.crate](third-party-sources/dtoa-short-0.3.5.crate) | [官方版本源码](https://static.crates.io/crates/dtoa-short/dtoa-short-0.3.5.crate) |
| option-ext | 0.2.0 | [option-ext-0.2.0.crate](third-party-sources/option-ext-0.2.0.crate) | [官方版本源码](https://static.crates.io/crates/option-ext/option-ext-0.2.0.crate) |

所有源码归档的 SHA-256、版本修订号、许可证文本路径和来源 URL 均保存在 `web-rust-dependencies.json` 与 `license-supplements.json`。未安装的其他平台 npm 可选包没有额外下载。

## 发布声明与官方当前许可证的差异

- `react-remove-scroll-bar@2.3.8` 的发布包声明 MIT、作者 Anton Korzunov；发布 gitHead 未提供 LICENSE。本包同时附上原始 package.json 和官方当前仓库的 MIT 全文（2025 年版权声明），来源 URL 与文本哈希已记录。
- `uri-js-replace@1.0.1` 的原始 package.json 声明 MIT；发布 gitHead 未提供 LICENSE。官方当前全文标题为 **MIT No Attribution（MIT-0）**、版权声明为 2025 andreinwald。两份原始声明均随附保存，清单中的已发布 `license: MIT` 没有被改写，也没有把当前 MIT-0 文本冒充为该历史发布包的 MIT 原文。
