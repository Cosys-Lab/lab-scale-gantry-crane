a = b'A: 0.00,V: 0.00,W: 0.00\r\n\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x04'
b = bytearray(a)
print(b)
b = b + bytearray(a)
print(b)
print(b[0])
del(b[0])
print(b[0])
print(b)

import re
import struct
regexp = re.compile(b'\x01(.{12})')
results = regexp.findall(b)
print(f"Results: {results}")
last = results[-1]

floats = struct.unpack('<fff', last)
print(floats)

b = b.split(last)[-1]
print(b)