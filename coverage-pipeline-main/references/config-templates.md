# 覆盖率流水线配置模板

## env.yaml 关键字段

```yaml
environment_id: ml307r-lab-01
module_model: ML307R
host_os: windows

paths:
  sdk_root: D:\ML307R\SDK
  artifact_dir: D:\ML307R\artifacts
  report_dir: D:\ML307R\reports

remote_access:
  enabled: true
  host: 192.168.3.128
  port: 22
  username: "52467"

build:
  command: cmd /c ML307R.bat DC
  forbid_commands:
    - cmd /c ML307R.bat DC ALL

flash:
  enabled: true
  platform: ASR
  tool:
    path: 需从 env.yaml 读取，不要硬编码（默认 D:\software\aboot-tools-*\adownload.exe）
  enter_download_mode:
    command: AT+MFORCEDL
  command_template:
    - "{tool.path}"
    - -q
    - -a
    - -u
    - -s
    - "115200"
    - -r
    - "{artifact.path}"
  success_keyword: aboot download engine stopped successfully

serial:
  at_port: COM16
  baudrate: 115200

coverage:
  reset_command: AT+COVERAGE=1
  summary_command: AT+COVERAGE?
  detail_command: AT+COVERAGE=DETAIL
  max_iterations: 3
  targets:
    module_stmt_percent: 75
    module_branch_percent: 55
    changed_stmt_percent: 90
    changed_branch_percent: 80

network:
  mqtt_broker: 8.137.154.246
  mqtt_port: 1883
```

## module_config.mqtt_at.yaml 关键字段

```yaml
module: mqtt_at
source:
  source_files:
    - onemo\at\src\cm_atcmd_mqtt.c
  related_files:
    - onemo\at\src\cm_atcmd_extern.c
    - onemo\at\inc\cm_coverage.h

coverage:
  id_ranges:
    stmt: {start: 100, end: 500}
    branch: {start: 1100, end: 1332}
  total_stub_count_hint: 635

at_commands:
  - name: AT+MQTTCFG
    format: 'AT+MQTTCFG="<key>",<conn_id>[,<value>]'
  - name: AT+MQTTCONN
    format: 'AT+MQTTCONN=<conn_id>,<host>,<port>,<client_id>,<user>,<pass>'
  # ... 其他命令

testing:
  mqtt_broker: {host: 8.137.154.246, port: 1883}
  max_iterations: 3
```

## module_config.http_at.yaml 关键字段

```yaml
module: http_at
source:
  source_files:
    - onemo\at\src\cm_atcmd_http.c
  related_files:
    - onemo\at\src\cm_atcmd_extern.c
    - onemo\at\inc\cm_coverage.h

coverage:
  id_ranges:
    stmt: {start: 200, end: 437}
    branch: {start: 2000, end: 2211}
  total_stub_count_hint: 450

at_commands:
  - name: AT+MHTTPCFG
    format: 'AT+MHTTPCFG="<key>",<http_id>[,<value>]'
  - name: AT+MHTTPCREATE
    format: 'AT+MHTTPCREATE="<url>"'
  - name: AT+MHTTPHEADER
    format: 'AT+MHTTPHEADER=<http_id>,<eof>,<length>,"<header>"'
  - name: AT+MHTTPCONTENT
    format: 'AT+MHTTPCONTENT=<http_id>,<eof>,<length>,"<data>"'
  - name: AT+MHTTPREQUEST
    format: 'AT+MHTTPREQUEST=<http_id>,<method>,<length>,"<path>"'
  - name: AT+MHTTPREAD
    format: 'AT+MHTTPREAD=<http_id>[,<type>,<length>]'
  - name: AT+MHTTPDEL
    format: 'AT+MHTTPDEL=<http_id>'
  - name: AT+MHTTPTERM
    format: 'AT+MHTTPTERM[=<http_id>]'
  - name: AT+MHTTPDLFILE
    format: 'AT+MHTTPDLFILE="<url>","<file>",<progress>[,"<range>"]'
  - name: AT+MHTTPDBG
    format: 'AT+MHTTPDBG=<level>'

testing:
  http_test_url: http://httpbin.org
  max_iterations: 3
```
