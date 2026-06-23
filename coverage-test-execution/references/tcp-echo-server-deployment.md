# TCP/UDP Echo Server 部署指南

## 用途
ML307R TCP 模块覆盖率测试需要可达的 echo server 来触发 MIPOPEN/MIPSEND/MIPRD 的完整路径。

## 快速部署

```bash
# SSH 到服务器
ssh root@<server_ip>

# 创建 echo server
cat > /tmp/echo_server.py << 'EOF'
#!/usr/bin/env python3
import socket, threading, os, signal

TCP_PORT = 9500
UDP_PORT = 9501

def tcp_echo(conn, addr):
    print(f'[TCP] Connected: {addr}', flush=True)
    try:
        while True:
            data = conn.recv(4096)
            if not data: break
            conn.sendall(data)
    except: pass
    finally:
        conn.close()
        print(f'[TCP] Disconnected: {addr}', flush=True)

def tcp_server():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('0.0.0.0', TCP_PORT))
    srv.listen(10)
    print(f'[TCP] Listening on {TCP_PORT}', flush=True)
    while True:
        conn, addr = srv.accept()
        threading.Thread(target=tcp_echo, args=(conn, addr), daemon=True).start()

def udp_server():
    srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    srv.bind(('0.0.0.0', UDP_PORT))
    print(f'[UDP] Listening on {UDP_PORT}', flush=True)
    while True:
        data, addr = srv.recvfrom(4096)
        srv.sendto(data, addr)

threading.Thread(target=tcp_server, daemon=True).start()
threading.Thread(target=udp_server, daemon=True).start()
with open('/tmp/echo_server.pid', 'w') as f: f.write(str(os.getpid()))
print(f'Echo server PID {os.getpid()}', flush=True)
signal.pause()
EOF

# 启动
nohup python3 /tmp/echo_server.py > /tmp/echo_server.log 2>&1 &

# 验证
echo "test" | nc -w 3 localhost 9500  # 应回显 "test"
```

## 端口选择
- 避开常用端口（7777/9000 可能被 WorkerMan 占用）
- 推荐 9500 (TCP) + 9501 (UDP)
- 防火墙/安全组需放行

## ML307R 连接测试
```python
# AT+MIPOPEN=0,"TCP","<server_ip>",9500,30,0
# 期望: OK → +MIPOPEN: 0,0
# AT+MIPSTATE=0
# 期望: +MIPSTATE: 0,"TCP","<server_ip>",9500,"CONNECTED"
```
