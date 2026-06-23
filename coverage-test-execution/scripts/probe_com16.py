import serial
import time

port = 'COM16'
ser = serial.Serial(port, 115200, timeout=1)
time.sleep(0.5)
ser.reset_input_buffer()
ser.write(b'AT\r\n')
time.sleep(0.8)
print(repr(ser.read(ser.in_waiting or 1)), flush=True)
ser.close()
