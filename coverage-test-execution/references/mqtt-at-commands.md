# MQTT AT 命令完整参考

## AT+MQTTCFG 配置

### 格式
```
AT+MQTTCFG="<key>",<conn_id>[,<value>]
```

### 支持的 key

| key | 值范围 | 说明 |
|-----|--------|------|
| version | 4 | 只支持 4（MQTT v3.1.1） |
| cid | 1-15 | PDP context ID |
| ssl | 0, 1 | SSL 开关 |
| keepalive | 0 或 60-65535 | 心跳间隔（秒） |
| clean | 0, 1 | 清除会话 |
| reconn | 0-3, 20-60, 0-1 | 重连次数, 间隔, 策略 |
| timeout | 1-120 | 超时时间（秒） |
| sndbuf | 2048-62780 | 发送缓冲区大小 |
| platsel | 0-3 | 平台选择（0=无, 1=OneNet, 2=Aliyun, 3=华为云） |
| retrans | 20-60, 0-3 | 重传间隔, 重传次数 |
| willoption | 0-1, 0-2, 0-1 | will_flag, will_qos, will_retain |
| willpayload | string, string | will_topic, will_message |
| pingreq | 60-86400 | 心跳间隔（秒） |
| pingresp | 0, 1 | 心跳回显开关 |
| encoding | 0-2, 0-1 | 输入格式, 输出格式 |
| cached | 0, 1 | 缓存模式 |
| query | - | 查询全部配置 |

### 示例
```
AT+MQTTCFG="version",0,4
AT+MQTTCFG="keepalive",0,60
AT+MQTTCFG="keepalive",0        # 查询
AT+MQTTCFG=?                    # 测试命令
```

## AT+MQTTCONN 连接

### 格式
```
AT+MQTTCONN=<conn_id>,<host>,<port>,<client_id>,<username>,<password>
```

### 异步响应
```
+MQTTURC: "conn",<conn_id>,<code>
```
- code=0: 连接成功
- code=1: 正在重连
- code=2: 客户端断开
- code=3: 服务器拒绝
- code=6: 网络异常

### 示例
```
AT+MQTTCONN=0,"8.137.154.246",1883,"test_client","",""
```

## AT+MQTTSUB 订阅

### 格式
```
AT+MQTTSUB=<conn_id>,<topic>,<qos>[,<topic2>,<qos2>...]
```

### 响应
```
+MQTTSUB: <conn_id>,<mid>
+MQTTURC: "suback",<conn_id>,<mid>,<code>
```

### 示例
```
AT+MQTTSUB=0,"test/topic",0
AT+MQTTSUB=0,"test/a",0,"test/b",1
```

## AT+MQTTPUB 发布

### 格式
```
AT+MQTTPUB=<conn_id>,<topic>,<qos>,<retain>,<dup>,<msg_len>,<message>
```

### 响应
```
+MQTTPUB: <conn_id>,<mid>,<length>
+MQTTURC: "puback",<conn_id>,<mid>,<dup>  # QoS=1
+MQTTURC: "pubrec",<conn_id>,<mid>,<dup>  # QoS=2
```

### 示例
```
AT+MQTTPUB=0,"test/topic",0,0,0,4,"data"
AT+MQTTPUB=0,"test/topic",1,0,0,11,"hello world"
```

## AT+MQTTPUBJSON JSON 发布

### 格式
```
AT+MQTTPUBJSON=<conn_id>,<topic>,<qos>,<retain>,<dup>,<method>,<msg_len>,<message>
```

### 示例
```
AT+MQTTPUBJSON=0,"test/json",0,0,0,"",13,"{\"key\":\"val\"}"
```

## AT+MQTTREAD 读取

### 格式
```
AT+MQTTREAD=<conn_id>[,<count>]
```

### 响应
```
+MQTTREAD: <conn_id>,<store_msgs>,<total_len>
+MQTTREAD: <conn_id>,<mid>,<topic>,<payload_len>,<payload>
```

## AT+MQTTUNSUB 取消订阅

### 格式
```
AT+MQTTUNSUB=<conn_id>,<topic>[,<topic2>...]
```

## AT+MQTTSTATE 状态查询

### 格式
```
AT+MQTTSTATE=<conn_id>
```

### 状态值
- 1: 正在连接
- 2: 已连接
- 3: 已断开

## AT+MQTTDISC 断开

### 格式
```
AT+MQTTDISC=<conn_id>
```

## AT+COVERAGE 覆盖率

```
AT+COVERAGE=1       # 重置并启用
AT+COVERAGE?        # 查询摘要
AT+COVERAGE=DETAIL  # 查询明细
```
