# Troll Application Development Framework 0.3

复制本目录 → 改 `trollapp.yml` → 把 Xcode 源码贴进 `App/` → 打包 IPA → 用 TrollStore 安装。不要打开 Apple 代码签名。

## 0. 环境（每台 Mac 一次）

```bash
brew install xcodegen ldid
xcode-select -p   # 能指到 Xcode
```

需要：macOS、Xcode、Python 3、真机侧已装 TrollStore。

## 1. 复制框架

把整个 `TrollApplicationDevelopmentFramework` 拷到你的工作目录。之后所有命令都在这个目录里跑。只需复制一次；`App/` 里可以同时放多个工程。

## 2. 在 Xcode 写业务（框架外）

照常新建/打开自己的 Xcode 工程写代码。不要用框架里自动生成的 `.xcodeproj` 当主工程长期改业务。

约定：

- `@main` 类型所在模块名，尽量与后面 `trollapp.yml` 里的 `app.name` 一致
- 最低系统版本不要低于 `app.min_ios`（默认 15.0）

### 第三方 SPM（Adjust / AppsFlyer / Firebase）

左侧 Package Dependencies 出现 `ios_sdk` 只表示仓库已加到 **工程**。还要把 library 链到 **Target**：

1. 选 Target `HelloTroll` → General → **Frameworks, Libraries, and Embedded Content** → **+**
2. 选 `AdjustSdk`（AppsFlyer 选 `AppsFlyerLib`）
3. 在代码里 `import` 并初始化（SwiftUI 用 `@UIApplicationDelegateAdaptor`）

不要用 Xcode 的 Archive / Export。TADF 不吃 `.xcodeproj`。

## 3. 把源码放进槽位

拷 **源码组**，不是工程根。例如 Xcode 工程是：

```text
xcode_project/sdk_test/HelloTroll/     # 工程根，有 .xcodeproj，不要拷这一层
  HelloTroll/                          # 源码组：.swift / Assets，拷这一层
```

```bash
rsync -a \
  --exclude='.DS_Store' \
  /Users/tm/zibo_project/workflow/develop_iosApp/xcode_project/sdk_test/HelloTroll/HelloTroll/ \
  App/HelloTroll/
```

新工程建议放到 `App/<新名字>/`，不要覆盖展位；然后把 `pack_source` 改成那个名字。

不要拷：

- `.xcodeproj` / `.xcworkspace` / `Package.resolved`
- 证书、描述文件、`*.mobileprovision`
- 工程里那份 `Info.plist`、`*.entitlements`（身份和权限由 yaml 生成）

SPM 包不会跟着源码走。在 `trollapp.yml` 用 `packages:` 再声明一次，打包时会重新拉。

## 4. 改全局配置 `trollapp.yml`

每次打包前改这一份（当前要打哪一个工程）：

```yaml
app:
  name: HelloTroll
  display_name: HelloTroll
  bundle_id: com.fyqs.HelloTroll
  version: "1.0.0"
  build: "1"
  min_ios: "15.0"

pack_source: HelloTroll

packages:
  - name: Adjust
    url: https://github.com/adjust/ios_sdk
    from: "5.8.0"
    product: AdjustSdk

frameworks:
  - AdSupport
  - AdServices
  - AppTrackingTransparency
  - StoreKit

info:
  usage:
    tracking: 用于广告归因。
```

`from` 用你在 Xcode 里实际解析到的主版本，不要写 `1.0.0`。Firebase Analytics 再加 `ldflags: ["-ObjC"]`。

`capabilities` 按需加减。常用：`platform`、`unsandboxed`、`sysctl`、`gestalt`、`get_task_allow`、`mcm`、`fs_root`、`wifi_info`。VPN 扩展把 `packet_tunnel` 设为 `true`。

## 5. 打包

```bash
./scripts/package_ipa.sh
```

产物按 `pack_source` 隔离，互不覆盖：

```text
work/<pack_source>/
  trollapp.used.yml
  Generated/
  project.yml
  <app.name>.xcodeproj/
  build/
  dist/<app.name>.ipa
```

换工程：改根目录 `trollapp.yml` 再打包。上一份 `work/<另一个目录>/` 仍在。`trollapp.used.yml` 只在 IPA 打成功后写入。有 `packages` 时本机需要能访问 GitHub。

## 6. 安装

把 `work/<pack_source>/dist/*.ipa` 拷到已装 TrollStore 的设备上安装。不要走 Apple 代码签名。

## 改代码后再打

改 Xcode 源码 → 覆盖拷进 `App/<pack_source>/` → 再跑 `./scripts/package_ipa.sh`。只改展示名、版本、权限、SPM 时，只动根目录 yaml 再打包即可。
