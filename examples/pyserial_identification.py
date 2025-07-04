import serial.tools.list_ports

ports = serial.tools.list_ports.comports()

for port in ports:
    print(f"Device: {port.device}")
    print(f"  Description: {port.description}")
    print(f"  HWID: {port.hwid}")
    print(f"  VID: {port.vid}")
    print(f"  PID: {port.pid}")
    print(f"  Serial Number: {port.serial_number}")
    print(f"  Manufacturer: {port.manufacturer}")
    print(f"  Product: {port.product}")
    print()