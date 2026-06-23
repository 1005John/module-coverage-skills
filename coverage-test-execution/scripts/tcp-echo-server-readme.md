# TCP echo server scripts
# Deploy to remote server for TCP coverage testing

## echo_server.py
TCP/UDP echo server for ML307R coverage testing.
- TCP port 9500: echo back whatever received
- UDP port 9501: echo back whatever received
- Deploy: `sshpass -p 'PASSWORD' scp echo_server.py root@SERVER:/tmp/`
- Run: `nohup python3 /tmp/echo_server.py > /tmp/echo_server.log 2>&1 &`
- Check: `netstat -tlnp | grep 9500`
- Current server: 8.137.154.246 (root)

## test_mipcfg.py
Quick diagnostic: test various MIPCFG command formats to find working syntax.
