"""
Bitmap 采集函数 - 用于精确覆盖率跟踪

从 AT+COVERAGE=2..9 输出中解析 MQTT/PWM 等模块的 bitmap，
计算每个 stub 是否命中。

使用方法：
1. 在测试脚本中导入此函数
2. 每个 case 前后调用 bitmap_snapshot() 计算增量
3. 增量为 0 说明该 case 没有新增覆盖
"""

import re
import time

def bitmap_snapshot(ser, module='MQTT'):
    """
    采集指定模块的 bitmap，返回 hit stub id 集合
    
    Args:
        ser: serial.Serial 对象
        module: 模块名 ('MQTT', 'PWM', 'TCP', 'HTTP', 'PING')
    
    Returns:
        (words_dict, hit_ids_set)
    """
    words = {}
    for cmd_value in range(2, 10):
        ser.reset_input_buffer()
        ser.write(f'AT+COVERAGE={cmd_value}\r\n'.encode())
        time.sleep(0.5)
        resp = ser.read(ser.in_waiting).decode('utf-8', errors='replace')
        
        m = re.search(
            rf'\+COVERAGE_DETAIL:\s*{module},(\d+),(\d+),([0-9A-Fa-f,]+)',
            resp
        )
        if m:
            base = int(m.group(2))
            hex_words = m.group(3).split(',')[:8]
            for off, word in enumerate(hex_words):
                try:
                    words[base + off] = int(word, 16)
                except ValueError:
                    pass
    
    # 判断命中
    ids = set()
    for word_index, word in words.items():
        for bit in range(32):
            sid = word_index * 32 + bit
            if word & (1 << bit):
                ids.add(sid)
    
    return words, ids


def summary(ser, module='MQTT'):
    """
    从 AT+COVERAGE? 返回中解析指定模块的汇总信息
    
    Returns:
        dict with stmt_percent, branch_percent, hit_stubs, total_stubs
    """
    ser.reset_input_buffer()
    ser.write(b'AT+COVERAGE?\r\n')
    time.sleep(0.5)
    resp = ser.read(ser.in_waiting).decode('utf-8', errors='replace')
    
    m = re.search(
        rf'{module}\((\d+)%,(\d+)%,(\d+)/(\d+)\)',
        resp
    )
    if not m:
        return {
            'stmt_percent': 0,
            'branch_percent': 0,
            'hit_stubs': 0,
            'total_stubs': 0,
            'raw': resp
        }
    
    return {
        'stmt_percent': int(m.group(1)),
        'branch_percent': int(m.group(2)),
        'hit_stubs': int(m.group(3)),
        'total_stubs': int(m.group(4)),
        'raw': resp
    }


def case_with_bitmap(ser, case_id, action, module='MQTT'):
    """
    执行单条 case，采集前后 bitmap，计算增量
    
    Args:
        ser: serial.Serial 对象
        case_id: case 标识
        action: callable(ser) -> response
        module: 模块名
    
    Returns:
        dict with id, response, before, after, new_ids, new_count
    """
    # 采集 before
    _, before_ids = bitmap_snapshot(ser, module)
    before_summary = summary(ser, module)
    
    # 执行 action
    print(f'CASE {case_id}')
    response = action(ser)
    
    # 采集 after
    _, after_ids = bitmap_snapshot(ser, module)
    after_summary = summary(ser, module)
    
    # 计算增量
    new_ids = sorted(after_ids - before_ids)
    new_count = after_summary['hit_stubs'] - before_summary['hit_stubs']
    
    print(f'CASE {case_id} NEW {new_count} hits={after_summary["hit_stubs"]}')
    
    return {
        'id': case_id,
        'response': response[:2000],
        'before_summary': before_summary,
        'after_summary': after_summary,
        'new_ids': new_ids,
        'new_count': new_count,
    }


# 使用示例
if __name__ == '__main__':
    import serial
    
    PORT = 'COM16'
    BAUD = 115200
    
    with serial.Serial(PORT, BAUD, timeout=0.8) as ser:
        time.sleep(0.5)
        ser.read_all()
        
        # 清零
        ser.write(b'AT+COVERAGE=1\r\n')
        time.sleep(1)
        ser.read_all()
        
        # 采集 bitmap
        words, ids = bitmap_snapshot(ser, 'MQTT')
        print(f'MQTT bitmap: {len(ids)} stubs hit')
        
        # 汇总
        sm = summary(ser, 'MQTT')
        print(f'MQTT summary: {sm}')
