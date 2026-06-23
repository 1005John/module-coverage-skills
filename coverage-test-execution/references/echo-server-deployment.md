# TCP Echo Server 部署与使用

## 何时需要
TCP/UDP 模块测试需要一个可达的 echo server 来验证数据收发。

## 已知 Echo Server (2026-06)
- 地址: 8.137.154.246
- TCP: 9500, UDP: 9501
- SSH: root / OneMo@2024
- 脚本: /tmp/echo_server.py

## 部署新 Echo Server

### 1. SSH 连接 (密码认证)
```bash
sshpass -p 'PASSWORD' ssh -o StrictHostKeyChecking=no root@SERVER_IP "command"
```

### 2. 上传脚本
```bash
sshpass -p 'PASSWORD' scp -o StrictHostKeyChecking=no echo_server.py root@SERVER_IP:/tmp/
```

### 3. Python Echo Server 脚本
```python
#!/usr/bin/env python3
import socket, threading, os, signal

TCP_PORT = 9500
UDP_PORT = 9501

def tcp_echo(conn, addr):
    try:
        while True:
            data = conn.recv(4096)
            if not data: break
            conn.sendall(data)
    except: pass
    finally: conn.close()

def tcp_server():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('0.0.0.0', TCP_PORT))
    srv.listen(10)
    while True:
        conn, addr = srv.accept()
        threading.Thread(target=tcp_echo, args=(conn, addr), daemon=True).start()

def udp_server():
    srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    srv.bind(('0.0.0.0', UDP_PORT))
    while True:
        data, addr = srv.recvfrom(4096)
        srv.sendto(data, addr)

if __name__ == '__main__':
    threading.Thread(target=tcp_server, daemon=True).start()
    threading.Thread(target=udp_server, daemon=True).start()
    with open('/tmp/echo_server.pid', 'w') as f: f.write(str(os.getpid()))
    signal.pause()
```

### 4. 启动 (nohup 后台)
```bash
sshpass -p 'PASSWORD' ssh root@SERVER "nohup python3 /tmp/echo_server.py > /tmp/echo_server.log 2>&1 &"
```

### 5. 验证
```bash
echo "test" | nc -w 3 SERVER_IP 9500  # 应回显 "test"
```

### 6. 重启
```bash
sshpass -p 'PASSWORD' ssh root@SERVER "kill \$(cat /tmp/echo_server.pid) 2>/dev/null; nohup python3 /tmp/echo_server.py > /tmp/echo_server.log 2>&1 &"
```

## 注意事项
- 检查端口是否被占用: `netstat -tlnp | grep PORT`
- 防火墙/安全组需放行 TCP+UDP 端口
- 8.137.154.246 上 7777 和 9000 被 WorkerMan 占用
