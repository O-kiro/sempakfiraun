import serial
import time

dwin_port = serial.Serial(
    port='/dev/serial0',
    baudrate=115200,
    timeout=0.1
)

# 1. Define your dynamic variables
bottle_amount = 12
can_amount = 5
total_point = 850


def send_data(address, value):
    """Converts a variable into DWIN hex format and sends it."""

    # Split the address into High and Low bytes
    addr_h = (address >> 8) & 0xFF
    addr_l = address & 0xFF

    # Split the variable's value into High and Low bytes
    val_h = (value >> 8) & 0xFF
    val_l = value & 0xFF

    # Construct the 8-byte write frame
    frame = [0x5A, 0xA5, 0x05, 0x82, addr_h, addr_l, val_h, val_l]

    # Send to display
    dwin_port.write(bytearray(frame))
    time.sleep(0.05)  # Small delay to ensure clean transmission


# --- TRANSMIT: Send the 3 variables to 3 different addresses ---

print(f"Sending data -> Bottles: {bottle_amount}, Cans: {can_amount}, Points: {total_point}")

# Send bottle_amount to Address 0x1000
send_data(0x1000, bottle_amount)

# Send can_amount to Address 0x1001
send_data(0x1001, can_amount)

# Send total_point to Address 0x1002
send_data(0x1002, total_point)

print("Variables sent successfully.")

# --- RECEIVE: Wait for 1 Byte Array from DWIN ---

print("Waiting for data from DWIN...")
try:
    while True:
        if dwin_port.in_waiting >= 9:
            incoming_bytes = dwin_port.read(9)
            frame = list(incoming_bytes)

            if frame[0] == 0x5A and frame[1] == 0xA5 and frame[3] == 0x83:
                # Reconstruct the received data back into normal Python variables
                recv_address = (frame[4] << 8) | frame[5]
                recv_value = (frame[7] << 8) | frame[8]

                print(f"Received -> Address: {hex(recv_address)}, Value: {recv_value}")
                break  # Exit after receiving 1 message

        time.sleep(0.01)

except KeyboardInterrupt:
    print("Stopped.")
finally:
    dwin_port.close()