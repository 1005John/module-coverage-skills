# ML302A Dev ASR 144 模块清单

## 环境

- Windows 服务器: 192.168.242.120 (Lenovo/123)
- 本地仓库路径: `C:\Users\Lenovo\Desktop\module_coverage_agent\repos\ml302a_dev_asr_144`
- AT 源码目录: `SDK\onemo\at\src\`

## 模块文件清单 (2026-06-25)

| 文件 | 大小 (bytes) | 建议优先级 | 备注 |
|------|-------------|-----------|------|
| cm_atcmd_extern.c | 157,456 | 必改 | AT+COVERAGE? 汇总入口，每加模块都要改 |
| cm_atcmd_mqtt.c | 106,880 | ✅ 已完成 | 635 桩 |
| cm_atcmd_audio.c | 101,691 | ⭐⭐⭐ | 大模块，依赖音频设备 |
| cm_atcmd_http.c | 73,194 | ✅ 已完成 | 450 桩 |
| cm_atcmd_ftp.c | 59,726 | ⭐⭐⭐ | 文件传输，状态机清晰 |
| cm_atcmd_asr.c | 57,158 | ⭐⭐ | 产品/配置模式，需谨慎 |
| cm_atcmd_cot.c | 54,664 | ⭐⭐ | LwM2M，可能依赖平台 |
| cm_atcmd_fs.c | 54,007 | ⭐⭐ | 文件系统，不依赖网络 |
| cm_atcmd_tcpip.c | 53,306 | ⭐⭐⭐ | TCP socket，已知有 crash bug |
| cm_atcmd_gnss.c | 38,691 | ⭐⭐ | 定位，依赖 GNSS 环境 |
| cm_atcmd_tts.c | 34,844 | ⭐⭐ | TTS 语音合成 |
| cm_atcmd_ssl.c | 34,111 | ⭐⭐ | SSL/TLS，可与 TCP/HTTP 组合 |
| cm_atcmd_gnss_cc1161w.c | 17,493 | ⭐ | GNSS 子模块 |
| cm_atcmd_wifiscan.c | 13,886 | ⭐ | WiFi 扫描，依赖环境 |
| cm_atcmd_dns.c | 12,732 | ⭐ | 小模块，适合练手 |
| cm_atcmd_cmdmp.c | 20,438 | ⭐ | 小模块 |
| cm_atcmd_lbs.c | 8,599 | ⭐ | 最小模块 |
| cm_atcmd_pwm.c | 7,469 | ⭐ | 小模块，硬件副作用可控 |
| cm_atcmd_ping.c | 6,355 | ⭐ | 最小模块 |

## 建议插桩顺序

### 第一批（练手验证流程）
1. **DNS** (12KB) — 小模块，命令少，容易验证完整流程
2. **Ping** (6KB) — 最小，快速验证
3. **PWM** (7KB) — 小模块

### 第二批（中等价值）
4. **SSL** (34KB) — 网络安全相关
5. **TTS** (34KB) — 音频功能
6. **FS** (54KB) — 文件系统，不依赖网络

### 第三批（高价值但复杂）
7. **TCP/IP** (53KB) — 网络核心，已知有 crash bug (MIPCLOSE/MIPMODE/MIPOPEN 冲突)
8. **FTP** (59KB) — 文件传输
9. **Audio** (101KB) — 大模块

## 桩 ID 分配建议

| 模块 | 语句桩 ID | 分支桩 ID |
|------|-----------|-----------|
| DNS | 800-849 | 2800-2849 |
| Ping | 850-879 | 2850-2879 |
| PWM | 880-909 | 2880-2909 |
| SSL | 910-999 | 2910-2999 |
| TTS | 1000-1049 | 3000-3049 |
| FS | 1050-1099 | 3050-3099 |

注意：避免与已有模块 ID 重叠（MQTT: 100-500/1100-1332, HTTP: 200-437/2000-2211, TCP: 500-799/2500-2661, EXT: 0-53/1100+）
