import serial
import time
import binascii
import tkinter as tk
from tkinter import ttk, messagebox

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


def send_message():
    try:
        slave_address = int(slave_address_entry.get())
        command = int(command_entry.get())
        data = data_entry.get().encode()
        master.send_frame(slave_address, command, data)
    except Exception as e:
        messagebox.showerror("Error", str(e))

if __name__ == "__main__":
    master_port = 'COM5'
    master = ModbusMaster(port=master_port, mode=ASCII_MODE)
    master.set_parameters(baudrate=9600, bytesize=8, parity='N', stopbits=1)
    
    root = tk.Tk()
    root.title("Modbus Master GUI")

    frame = ttk.Frame(root, padding="10")
    frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    ttk.Label(frame, text="Slave Address:").grid(column=1, row=1, sticky=tk.W)
    slave_address_entry = ttk.Entry(frame, width=25)
    slave_address_entry.grid(column=2, row=1, sticky=(tk.W, tk.E))

    ttk.Label(frame, text="Command:").grid(column=1, row=2, sticky=tk.W)
    command_entry = ttk.Entry(frame, width=25)
    command_entry.grid(column=2, row=2, sticky=(tk.W, tk.E))

    ttk.Label(frame, text="Data:").grid(column=1, row=3, sticky=tk.W)
    data_entry = ttk.Entry(frame, width=25)
    data_entry.grid(column=2, row=3, sticky=(tk.W, tk.E))

    send_button = ttk.Button(frame, text="Send", command=send_message)
    send_button.grid(column=2, row=4, sticky=tk.W)

    response_text = tk.StringVar()
    response_label = ttk.Label(frame, textvariable=response_text)
    response_label.grid(column=1, row=5, columnspan=2, sticky=(tk.W, tk.E))

    root.mainloop()