# ReliableData.bin 缺失修复

## 问题

`ML307R.bat DC` 编译到最后打包阶段报：
```
Opening image "rd" from "D:\ML307R\SDK\tavor\Arbel\bin\ReliableData.bin" ...
error: open raw image "rd" failed.
FAILED: generate release package failed!
```

编译本身成功（.o 和 .axf 都生成），只是 release zip 打包失败。

## 原因

ReliableData.bin 是由 `generate_reliabledata.bat` + `generate_reliabledata.pl` 生成的。当：
- `DC ALL` 清空了 bin/ 目录
- Perl 脚本执行环境不完整（缺少 .gki 文件或 PATH 不含 Perl）
- build 目录下缺少 `TTPCom_NRAM2_CUSTOMIZATION_DATA.gki`

时，.bin 文件不会生成。

## 修复方法

### 方法 1：重新运行 generate_reliabledata（推荐）
```cmd
set PATH=D:\ML307R\SDK\tools\win32\Perl\bin;D:\ML307R\SDK\tools\win32;%PATH%
cd /d D:\ML307R\SDK\tavor\Arbel\build
copy ReliableData\reduce\TTPCom_NRAM2_CUSTOMIZATION_DATA.gki TTPCom_NRAM2_CUSTOMIZATION_DATA.gki /Y
perl generate_reliabledata.pl DM_THIN_SINGLE_SIM_NO_SMS_LTEONLY 3.1.0 Z2A0
copy ReliableData.bin ..\..\bin\ /Y
```

### 方法 2：从 ps.7z 恢复
```cmd
cd /d D:\ML307R\SDK
7z x tavor\Arbel\CRANE_SDK_LIB\DM_THIN_SINGLE_SIM_NO_SMS_LTEONLY\ps.7z -o. -y ReliableData.bin
copy ReliableData.bin tavor\Arbel\bin\ /Y
```

### 方法 3：再次运行 DC 编译
有时第二次 DC 编译会自动修复（因为第一次 DC 已经生成了中间产物）。如果第一次报此错误，直接再跑一次 `ML307R.bat DC` 即可。

## 验证

```cmd
dir D:\ML307R\SDK\tavor\Arbel\bin\ReliableData.bin
```
文件应存在且 > 0 字节（通常 8KB）。
