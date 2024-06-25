import serial
import binascii

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

class ModbusSlave:
    def __init__(self, port, address, mode=ASCII_MODE):
        self.port = serial.Serial(port)
        self.address = address
        self.mode = mode
        self.timeout = 1.0
        self.running = False
        self.character_timeout = 0.01

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
            frame = self.read_with_timeout()
            if self.mode == ASCII_MODE:
                self.handle_ascii_frame(frame)
            else:
                self.handle_rtu_frame(frame)

    def read_with_timeout(self):
        response = bytearray()
        while True:
            char = self.port.read(1)
            if not char:
                break
            response += char
            self.port.timeout = self.character_timeout  # Set timeout for next character
        return response

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
                print("Matching lrc values")
                slave_address = int(data[0:2], 16)
                if slave_address == self.address or slave_address == 0:
                    print("Matching slave address")
                    self.process_command(binascii.unhexlify(data))
            else:
                print("LRC validation failed")

    def handle_rtu_frame(self, frame):
        print(frame)
        if len(frame) >= 3:
            data, crc_received = frame[:-2], frame[-2:]
            print("===============Processing Message================")
            print(f"Frame: {frame}")
            print(f"Data: {data}")
            print(f"CRC: {bytes(crc_received)}")
            print(f"Calulcate Crc: {calculate_crc(data)}")
            if calculate_crc(data) == bytes(crc_received):
                slave_address = data[0]
                print("Matching crc values")
                if slave_address == self.address or slave_address == 0:
                    print("Matching slave address")
                    self.process_command(data)

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
    slave_port = 'COM6'

    slave = ModbusSlave(port=slave_port, address=1, mode=RTU_MODE)
    slave.set_parameters(baudrate=9600, bytesize=8, parity='N', stopbits=1)
    slave.start()