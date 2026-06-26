---
name: coverage-build-flash
description: "通信模组固件编译与烧录技能，支持增量编译、ASR 烧录、AT 口验证"
triggers:
  - "编译"
  - "烧录"
  - "flash"
  - "DC 编译"
---

# 固件编译与烧录

## When to Use
- 插桩文件已准备好，需要编译固件
- 固件已生成，需要烧录到模组
- 烧录后需要验证 AT 口和覆盖率

## 部署位置

**编译部分** → 编译服务器 (192.168.242.120): armcc/gnumake 编译 + release.zip 打包
**烧录部分** → 测试电脑 (172.20.162.21): adownload.exe + COM16 串口

固件传输：编译服务器 → Mac(跳板) → 测试电脑（scp 两跳，详见 DEPLOYMENT.md）

## 前置条件

- Windows 测试机 SSH 可达（ML307C: 172.20.162.21:22 用户 52467 无密码；ML307R: 192.168.3.128:22）
- SDK 路径 D:\ML307R\SDK
- ARM 编译器已授权（tools\win32\ARM_Compiler_5）
- aboot-tools 烧录工具已安装

## 编译

### ML307C 编译命令
```cmd
cd /d C:\Users\Lenovo\Desktop\module_coverage_agent\repos\ml302a_dev_asr_144\SDK
ML307C.bat DC-CN ALL      # 全量编译（~5 分钟）
ML307C.bat DC-CN           # 增量编译（不推荐，可能不触发重编）
```

- 变体：DC-CN（中国版）、DL-CN、ML-CN、DC-EM（海外版）
- 产物：`target\ML307C-DC-CN-MBRH1S00\ML307C-DC-CN-MBRH1S00_*_release.zip`
- DC ALL 会从 ps.7z 恢复源文件，但 SDK 中没有 ps.7z 时不会覆盖插桩修改

### ML307R 编译命令
```cmd
cd /d D:\ML307R\SDK
ML307R.bat DC          # 增量编译（推荐，~2 分钟）
ML307R.bat DC ALL      # 全量编译（禁止！会覆盖插桩文件）
```

### 编译前必须清理的缓存（ML307C）

修改 .h 或 .c 后，必须删除 .o、.d、.pp、pack_c.via 和 **.lib**：

```cmd
:: ⚠️ .lib 路径在 obj_PMD2NONE/ 下（不在 obj_onemo_onemo/ 下！）
del /q C:\Users\Lenovo\Desktop\module_coverage_agent\repos\ml302a_dev_asr_144\SDK\tavor\Arbel\obj_PMD2NONE\onemo-onemo.lib

:: AT 命令层 .o + 依赖文件
del /q C:\Users\Lenovo\Desktop\module_coverage_agent\repos\ml302a_dev_asr_144\SDK\tavor\Arbel\obj_PMD2NONE\obj_onemo_onemo\obj_onemo_at\cm_atcmd_ping.*

:: 覆盖率模块 .o（修改 cm_coverage.h 或 cm_coverage.c 时必须删）
del /q C:\Users\Lenovo\Desktop\module_coverage_agent\repos\ml302a_dev_asr_144\SDK\tavor\Arbel\obj_PMD2NONE\obj_onemo_onemo\obj_onemo_coverage\cm_coverage.*

:: pack_c.via
del /q C:\Users\Lenovo\Desktop\module_coverage_agent\repos\ml302a_dev_asr_144\SDK\tavor\Arbel\obj_PMD2NONE\obj_onemo_onemo\obj_onemo_at\pack_c.via
```

**⚠️ .lib 路径陷阱（2026-06-26 实战）**：只删 `.o` 不够！`.lib` 文件在 `obj_PMD2NONE\onemo-onemo.lib`（不在 `obj_PMD2NONE\obj_onemo_onemo\` 下）。如果 .lib 不删，链接器用旧 .lib 中的旧 .o，新代码不进固件。**验证方法**：`fromelf -c cm_atcmd_ping.o | findstr cm_cov_hit` 确认 .o 有 BL 调用；如果 .o 有但固件没有 → .lib 未重建。

### 编译产物验证
```cmd
:: .o 文件存在且 > 0 字节
dir D:\ML307R\SDK\tavor\Arbel\obj_PMD2NONE\obj_onemo_onemo\obj_onemo_at\cm_atcmd_http.o
:: .axf 链接产物
dir D:\ML307R\SDK\tavor\Arbel\bin\*.axf
:: 固件 zip
dir /b D:\ML307R\SDK\target\ML307R-DC-MBRH0S01\*release.zip
```

### 常见编译错误

| 错误 | 原因 | 修复 |
|------|------|------|
| #111-D statement is unreachable | COV_STMT 在 return/break/CM_RETURN 后 | 删除该桩 |
| #127 expected a statement | COV_STMT 在单行 if body 前 | 改用 if+{ } 或跳过 |
| #165 too few arguments | COV_STMT 在函数参数列表中 | 跳过该行 |
| #167 argument type void | COV_STMT 在多行函数调用中间 | 跳过该行 |
| L6218E Undefined symbol | 变量声明为 static 但被 extern 引用 | 去掉 static |
| open raw image "rd" failed | ReliableData.bin 缺失 | copy SDK 根目录的 ReliableData.bin 或 AbootTool/releasepackage/ 的到 bin/ |

## 烧录流程（含 adownload 路径）

### adownload.exe 路径
ML307R 测试机上的完整路径（2026-06-22 验证）：
```
D:\software\aboot-tools-2023.04.03\aboot-tools-2023.04.03\aboot-tools-2023.04.03-win-x86\aboot-tools-2023.04.03-win-x86\adownload.exe
```

### 完整烧录流程
1. **发送 AT+MFORCEDL** — 用 Python serial 发送，等待 3 秒
2. **确认下载设备出现** — `wmic path Win32_PnPEntity where "Caption like '%ASR%'" get Caption` 应显示 `ASR Serial Download Device (COMx)`
3. **执行 adownload**:
   ```
   cd /d D:\ML307R\SDK\target\ML307R-DC-MBRH0S01
   adownload.exe -q -u -a -s 115200 <release.zip>
   ```
4. **等待模块重启** — adownload 完成后模块可能不会自动重启（停留在 COM15 下载设备状态），需要**手动拔插 USB**
5. **验证** — 等待 COM16 恢复，发送 AT → OK → AT+MSWVER → AT+COVERAGE?

### 关键 Pitfall: 模块不自动重启
烧录成功（"all finished" + "SUCCEEDED"）后，模块可能停留在 ASR Serial Download Device (COM15) 状态。
`wmic` 检查：如果还显示 COM15 而非 COM16，需要物理断电重启。

### 关键 Pitfall: COM 端口占用
烧录后 adownload.exe 进程可能未退出，占住 COM 端口。先 `taskkill /f /im adownload.exe` 再尝试打开 COM16。

### 烧录后验证

```python
# AT 口连通
s.write(b'AT\r\n')  # 期望: OK
# 版本确认
s.write(b'AT+MSWVER\r\n')  # 期望: 包含版本号
# 覆盖率启用
s.write(b'AT+COVERAGE=1\r\n')  # 期望: OK
# 覆盖率查询
s.write(b'AT+COVERAGE?\r\n')  # 期望: +COVERAGE: EXT(...) MQTT(...) HTTP(...) ALL(...)
# Bitmap 查询（如果固件支持）
for i in range(2, 10):
    s.write(f'AT+COVERAGE={i}\r\n'.encode())  # 期望: +COVERAGE_DETAIL: MQTT,...
```

### Bitmap 接口验证

如果 `AT+COVERAGE=2..9` 返回 `ERROR`，说明固件不支持 bitmap 分块输出。需要：
1. 检查 `cm_atcmd_extern.c` 是否有 `AT+COVERAGE=2..9` 的处理逻辑
2. 检查 `cov_mqtt_bitmap` 是否被 extern 声明
3. 重新编译烧录

**期望输出**：
```
AT+COVERAGE=2
+COVERAGE_DETAIL: MQTT,0,0,00000000,00000000,00000000,1D0003F0,...
OK
```

### 常见 Pitfall

1. **DC ALL 会覆盖插桩文件** — 永远用 DC（增量），手动删 .o 触发重编
2. **cm_coverage.c 的 COV_TOTAL_STUBS 必须 >= 最大桩 ID+1** — HTTP 分支桩到 2211，必须设 2500
3. **cm_atcmd_extern.c 有本地 cm_cov_hit()** — 不是用 cm_coverage.c 的，其 COV_TOTAL_STUBS 也需同步更新
4. **AT+COVERAGE? 的 output buffer 只有 64 字节** — 新增模块后需扩大到 256
5. **HTTP 覆盖率计数器在 cm_atcmd_http.c 中定义** — 需 extern 声明 + 在 sprintf 中报告
6. **单行 if/else 无花括号** — 插桩脚本不能在 body 前插 COV_STMT
7. **CM_RETURN/break 后的 COV_STMT** — 编译器报 unreachable error
8. **ReliableData.bin 缺失** — DC ALL 后 bin 目录被清空，需从 SDK 根目录复制或重跑 DC 自愈
9. **adownload.exe 烧录后占用串口** — 烧录完成后 adownload.exe 可能不退出，导致 COM16 无法打开。解决：`taskkill /F /IM adownload.exe`。症状：`SerialException: could not open port 'COM16': OSError(22)`
10. **QCOM_V1.6.exe 占用串口** — 如果测试机上运行了 QCOM 工具，它会占用 COM16。解决：`taskkill /F /IM QCOM_V1.6.exe`
11. **烧录后需等待模组重启** — adownload 完成后需等待 5-10 秒，模组才会重启并枚举 USB 串口。如果立即打开 COM16 会报 "设备未就绪"

### 非 AT 模块的 .mak 修改

当需要对非 AT 模块（如 cm_http、cm_mqtt）进行插桩时，需修改其 .mak 文件：

```makefile
# 在 PACKAGE_INC_PATHS 中添加：
$(BUILD_ROOT)/onemo/coverage/inc

# 在 PACKAGE_DFLAGS 中添加：
-DCM_COVERAGE_ENABLE
```

**关键**：修改 .mak 后必须删除该模块的 `pack_c.via` 和所有 `.o` 文件：
```cmd
del /q D:\ML307R\SDK\tavor\Arbel\obj_PMD2NONE\obj_onemo_onemo\obj_onemo_<module>\*.*
```

否则增量编译不会重编该模块（.mak 变更不触发依赖检查）。

## 固件传输（编译服务器 → 测试电脑）

当固件在编译服务器(192.168.242.120)上而测试电脑(172.20.162.21)需要烧录时，两台机器不在同一子网，需两跳传输：

```bash
# 步骤 1: 编译服务器上 copy 到简单路径（避免 Windows 长路径和中文路径问题）
sshpass -p '123' ssh -o StrictHostKeyChecking=no Lenovo@192.168.242.120 \
  "cmd /c \"copy C:\\Users\\Lenovo\\Desktop\\...\\<firmware>.zip C:\\Users\\Lenovo\\fw.zip /Y\""

# 步骤 2: scp 到 Mac（用正斜杠路径）
sshpass -p '123' scp -o StrictHostKeyChecking=no \
  'Lenovo@192.168.242.120:C:/Users/Lenovo/fw.zip' /tmp/fw.zip

# 步骤 3: scp 到测试电脑
scp /tmp/fw.zip 52467@172.20.162.21:"D:/通信模组/at_kb_runs/<firmware>.zip"
```

**注意**: scp 直接用 Windows 反斜杠路径会失败，必须用正斜杠 `C:/Users/...`。

## 常见 Pitfalls

1. **DC ALL 会从 ps.7z 恢复源文件** — 所有插桩修改会被覆盖
2. **SSH 执行 bat 需要 cmd /c 前缀** — `cmd /c ML307R.bat DC`
3. **ReliableData.bin 缺失** — DC ALL 后 bin/ 被清空。**自愈方法**：再跑一次 DC 编译自动生成。不需要手动提取。
4. **编译成功但 release zip 未生成** — `target\ML307R-DC-MBRH0S01\` 只有 `DBG.7z` 说明打包失败（通常 ReliableData.bin 问题），再跑 DC 即可。
5. **增量编译不检测 .mak 修改** — 改 .mak 后需手动删 .o 和 pack_c.via
6. **armcc --diag_error=warning** — 不可达代码是 error 不是 warning
7. **编译 < 5 分钟可能有模块没编进去** — 全量编译正常 15-18 分钟
8. **⚠️ L6218E Undefined symbol 链接错误** — `extern volatile unsigned int cov_xxx_stmt_hits` 在 cm_atcmd_extern.c 中声明但模块 .c 文件未定义。修复：在模块 .c 中添加 `volatile unsigned int cov_xxx_stmt_hits = 0;`。详见 coverage-instrumentation skill 的"新模块三步漏一不可"。
9. **⚠️ ReliableData.bin 缺失导致 release zip 打包失败** — DC ALL 清空 bin/ 后 ReliableData.bin 未重新生成。修复方法（按优先级）：
   a. 再跑一次 DC 编译（有时自愈）
   b. 手动生成：`cd build && perl generate_reliabledata.pl DM_THIN_SINGLE_SIM_NO_SMS_LTEONLY 3.1.0 Z2A0 && copy ReliableData.bin ..\bin\`
   c. 从 build\ 目录复制已有的 ReliableData.bin 到 bin\
10. **⚠️ 烧录后模块卡在下载模式（COM15）** — adownload.exe 烧录 100% SUCCEEDED 后模块可能停留在 ASR Serial Download Device (COM15)。需要物理拔插 USB 才能恢复 AT 模式 (COM16)。**远程无法解决**，必须用户手动操作。
11. **⚠️ COM 端口被占用** — `PermissionError(13, 'Access is denied')` 表示 COM 被其他进程占用。先 `taskkill /F /IM adownload.exe` 和 `taskkill /F /IM python.exe`，等待 3 秒后重试。
7. **adownload.exe 路径** — 172.20.162.21 上路径: `D:\software\aboot-tools-2023.04.03\aboot-tools-2023.04.03\aboot-tools-2023.04.03-win-x86\aboot-tools-2023.04.03-win-x86\adownload.exe`
8. **烧录后模块不自动重启** — adownload 完成后模块停在 ASR Serial Download Device (COM15)，需物理拔插 USB 才能回到 AT 模式 (COM16)
9. **烧录后 AT 口 PermissionError** — adownload 进程可能残留，需 `taskkill /f /im adownload.exe` 后再等模块重启
7. **⚠️ 只删 .d/.pp 不删 .o 导致编译系统跳过重编** — gnumake 检查 .o 时间戳，若 .o 存在且新于源码就不重编。清理缓存必须 `.o` + `.d` + `.pp` + `pack_c.via` 一起删
8. **⚠️ pack_c.via 不删导致增量编译不生效** — 修改 .mak 文件（如加 `-DCM_COVERAGE_ENABLE` 或 include 路径）后，`pack_c.via` 缓存了旧编译选项。必须删除对应模块目录下的 `pack_c.via` 和所有 `.o`
9. **⚠️ adownload.exe 烧录后 COM 端口被锁定** — 进程退出后端口可能仍被占用。烧录完成后用 `taskkill /f /im adownload.exe` 强制释放端口
10. **⚠️ 模块烧录后不自动重启** — ASR 平台烧录 100% SUCCEEDED 后模块可能停留在下载模式（COM15 仍显示 ASR Serial Download Device）。需要物理断电重启（拔插 USB）才能回到 AT 模式（COM16）
11. **⚠️ onemo-at.lib 打包时序** — ARM SDK 使用静态库 (onemo-at.lib) 链接最终固件。如果 .lib 在 release ZIP 打包之后才重建，新代码不会进入固件。**验证方法**：`findstr cm_cov_hit *.axf` — 有输出=链接正确，无输出=.lib 未包含新 .o。**解决方案**：用 `ML307R.bat DC ALL` 全量重建，确保 .lib 在打包之前完成。
12. **⚠️ SSH 环境下 adownload.exe 卡住** — USB 烧录工具需要直接 USB 访问，通过 SSH 执行会永久卡住。必须由用户手动在测试机上执行烧录命令。
13. **⚠️ .lib 路径不在 obj_onemo_onemo/ 下（2026-06-26 实战）** — `onemo-onemo.lib` 在 `obj_PMD2NONE/` 下（`obj_PMD2NONE\onemo-onemo.lib`），不在 `obj_PMD2NONE\obj_onemo_onemo\` 下。只删 `.o` 不删 `.lib` 会导致链接器用旧 .lib 中的旧 .o，新代码不进固件。**症状**：fromelf 确认 .o 有 `BL cm_cov_hit` 但固件中覆盖率始终为 0。**修复**：删除 `.lib` 后全量重编。
   copy ReliableData\reduce\TTPCom_NRAM2_CUSTOMIZATION_DATA.gki TTPCom_NRAM2_CUSTOMIZATION_DATA.gki /Y
   perl generate_reliabledata.pl DM_THIN_SINGLE_SIM_NO_SMS_LTEONLY 3.1.0 Z2A0
   ```
   3. **ReliableData.bin 缺失** — DC ALL 后 bin/ 被清空。**自愈方法**：再跑一次 DC 编译自动生成。不需要手动提取。
   4. **编译成功但 release zip 未生成** — `target\ML307R-DC-MBRH0S01\` 只有 `DBG.7z` 说明打包失败（通常 ReliableData.bin 问题），再跑 DC 即可。
   5. **增量编译不检测 .mak 修改** — 改 .mak 后需手动删 .o 和 pack_c.via
   6. **armcc --diag_error=warning** — 不可达代码是 error 不是 warning
   7. **编译 < 5 分钟可能有模块没编进去** — 全量编译正常 15-18 分钟

## 验证清单

- [ ] .o 文件存在且 > 0 字节
- [ ] .axf 文件存在
- [ ] release.zip 文件存在
- [ ] 烧录成功（aboot stopped successfully）
- [ ] AT 口响应 OK
- [ ] AT+MSWVER 返回预期版本
- [ ] AT+COVERAGE? 显示正确的总桩数
