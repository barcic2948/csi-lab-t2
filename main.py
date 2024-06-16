import serial
import time
import binascii
import threading

ASCII_MODE = 'ASCII'
RTU_MODE = 'RTU'

MASTER = 'Master'
SLAVE = 'Slave'

def calculate_lrc(data):
    lrc = 0
    for byte in data:
        lrc += byte
    lrc = ((lrc ^ 0xFF) + 1) & 0xFF
    return lrc

def calculate_crc(data):
    crc = 0xFFFF
    for pos in data:
        crc ^= pos
        for _ in range(8):
            if (crc & 1) != 0:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc.to_bytes(2, byteorder='little')

def ascii_to_rtu(frame):
    return binascii.unhexlify(frame)

def rtu_to_ascii(frame):
    return binascii.hexlify(frame).upper()

class ModbusMaster:
    def __init__(self, port, mode=ASCII_MODE):
        self.port = serial.Serial(port)
        self.mode = mode
        self.timeout = 1.0
        self.retransmissions = 3
        self.transaction_timeout = 5.0

    def set_parameters(self, baudrate, bytesize, parity, stopbits):
        self.port.baudrate = baudrate
        self.port.bytesize = bytesize
        self.port.parity = parity
        self.port.stopbits = stopbits

    def send_frame(self, slave_address, command, data):
        if self.mode == ASCII_MODE:
            frame = self.prepare_ascii_frame(slave_address, command, data)
        else:
            frame = self.prepare_rtu_frame(slave_address, command, data)
        
        retries = 0
        while retries <= self.retransmissions:
            print(f"Master sending frame: {frame}")
            self.port.write(frame)

            if slave_address == 0 or command == 1:
                print("=================Master complete=================")
                return True
            
            print("===============Master Awaiting RES===============")
            if self.receive_response():
                print("=================Master complete=================")
                return True
            retries += 1
            print("============FAILED TO OBTAIN RESPONSE============")
            print(f"Retry: {retries}")
        return False

    def prepare_ascii_frame(self, slave_address, command, data):
        frame_data = f'{slave_address:02X}{command:02X}{binascii.hexlify(data).decode()}'
        lrc = calculate_lrc(binascii.unhexlify(frame_data))
        frame = f':{frame_data}{lrc:02X}\r\n'
        return frame.encode()

    def prepare_rtu_frame(self, slave_address, command, data):
        frame = bytes([slave_address, command]) + data
        frame += calculate_crc(frame)
        return frame

    def receive_response(self):
        self.port.timeout = self.transaction_timeout
        response = self.port.read_until(b'\n' if self.mode == ASCII_MODE else b'')
        print(f"Master received response: {response}")
        if self.mode == ASCII_MODE:
            return self.validate_ascii_frame(response)
        else:
            return self.validate_rtu_frame(response)

    def validate_ascii_frame(self, frame):
        if frame.startswith(b':') and frame.endswith(b'\r\n'):
            data_with_lrc = frame[1:-2]
            lrc = int(frame[-4:-2], 16)
            data = data_with_lrc[:-2]
            binary_data = binascii.unhexlify(data)
            calculated_lrc = calculate_lrc(binary_data)
            
            print("===============Processing Response===============")
            print(f"Data with LRC: {data_with_lrc}")
            print(f"Data: {data}")
            print(f"LRC: {lrc}")
            print(f"Binary data: {binary_data}")
            print(f"calculated lrc: {calculated_lrc}")

            if calculated_lrc == lrc:
                self.presentResponse(binary_data[2:])
                return True
            else:
                self.presentExcpetion("Bad lrc")
                return False
        self.presentExcpetion("Bad frame")
        return False

    def validate_rtu_frame(self, frame):
        if len(frame) >= 5:
            data, crc_received = frame[:-2], frame[-2:]
            if calculate_crc(data) == crc_received:
                return True
        return False
    
    def presentResponse(self, text):
        print("===============Processing Response===============")
        print(f"Master received text: {text.decode()}")
        
    def presentExcpetion(self, reason):
        print("==================Bad  response==================")
        print(f"Reason: {reason}")

class ModbusSlave:
    def __init__(self, port, address, mode=ASCII_MODE):
        self.port = serial.Serial(port)
        self.address = address
        self.mode = mode
        self.timeout = 1.0
        self.running = False

    def set_parameters(self, baudrate, bytesize, parity, stopbits):
        self.port.baudrate = baudrate
        self.port.bytesize = bytesize
        self.port.parity = parity
        self.port.stopbits = stopbits

    def start(self):
        self.running = True
        self.listen()

    def stop(self):
        self.running = False

    def listen(self):
        while self.running:
            self.port.timeout = None
            frame = self.port.read_until(b'\n' if self.mode == ASCII_MODE else b'')
            print(f"Slave received frame: {frame}")
            if self.mode == ASCII_MODE:
                self.handle_ascii_frame(frame)
            else:
                self.handle_rtu_frame(frame)

    def handle_ascii_frame(self, frame):
        if frame.startswith(b':') and frame.endswith(b'\r\n'):

            data_with_lrc = frame[1:-2]
            lrc = int(frame[-4:-2], 16)
            data = data_with_lrc[:-2]
            binary_data = binascii.unhexlify(data)
            calculated_lrc = calculate_lrc(binary_data)
            
            print("===============Processing Message================")
            print(f"Data with LRC: {data_with_lrc}")
            print(f"Data: {data}")
            print(f"LRC: {lrc}")
            print(f"Binary data: {binary_data}")
            print(f"Calulcate lrc: {calculated_lrc}")

            if calculated_lrc == lrc:
                slave_address = int(data[0:2], 16)
                if slave_address == self.address or slave_address == 0:
                    self.process_command(binascii.unhexlify(data))
            else:
                print("LRC validation failed")

    def handle_rtu_frame(self, frame):
        if len(frame) >= 5:
            data, crc_received = frame[:-2], frame[-2:]
            if calculate_crc(data) == crc_received:
                slave_address = data[0]
                if slave_address == self.address or slave_address == 0:
                    self.process_command(data[1:])

    def process_command(self, data):
        command = data[1]
        if command == 1:
            self.write_text(data[2:])
        elif command == 2:
            self.read_text()

    def write_text(self, text):
        print(f"Slave received text: {text.decode()}")
        print("=================Complete Slave==================")

    def read_text(self):
        text = "Sample text from slave"
        response = self.prepare_response(2, text.encode())
        print("==============Completed processing===============")
        print(f"Slave sending response: {response}")
        self.port.write(response)

    def prepare_response(self, command, data):
        if self.mode == ASCII_MODE:
            frame = self.prepare_ascii_frame(self.address, command, data)
        else:
            frame = self.prepare_rtu_frame(self.address, command, data)
        return frame

    def prepare_ascii_frame(self, slave_address, command, data):
        frame_data = f'{slave_address:02X}{command:02X}{binascii.hexlify(data).decode()}'
        lrc = calculate_lrc(binascii.unhexlify(frame_data))
        frame = f':{frame_data}{lrc:02X}\r\n'
        return frame.encode()

    def prepare_rtu_frame(self, slave_address, command, data):
        frame = bytes([slave_address, command]) + data
        frame += calculate_crc(frame)
        return frame

if __name__ == "__main__":
    master_port = 'COM5'
    slave_port = 'COM6'

    master = ModbusMaster(port=master_port, mode=ASCII_MODE)
    master.set_parameters(baudrate=9600, bytesize=8, parity='N', stopbits=1)
    
    slave = ModbusSlave(port=slave_port, address=1, mode=ASCII_MODE)
    slave.set_parameters(baudrate=9600, bytesize=8, parity='N', stopbits=1)
    
    slave_thread = threading.Thread(target=slave.start)
    slave_thread.start()
    

    time.sleep(1)

    master.send_frame(slave_address=1, command=1, data=b'Hello, Slave')
    time.sleep(1)
    master.send_frame(slave_address=1, command=2, data=b'')
    
    time.sleep(2)
    
    slave.stop()
    slave_thread.join()
    exit()
