import serial
import time

# --- INITIALIZATION ---
# NOTE: This must be run on the Raspberry Pi.
# If testing on Windows with a USB adapter, change '/dev/serial0' to 'COM3' (or your active COM port).
try:
    dwin_port = serial.Serial(
        port='/dev/serial0',
        baudrate=115200,
        timeout=0.1
    )
    print("Serial port opened successfully.")
except Exception as e:
    print(f"Error opening serial port: {e}")
    exit()


# --- FUNCTIONS ---

def send_data(address, value):
    """Sends a standard 2-byte integer to a specific DWIN address."""
    addr_h = (address >> 8) & 0xFF
    addr_l = address & 0xFF
    val_h = (value >> 8) & 0xFF
    val_l = value & 0xFF

    frame = [0x5A, 0xA5, 0x05, 0x82, addr_h, addr_l, val_h, val_l]
    dwin_port.write(bytearray(frame))
    time.sleep(0.05)


def send_text(address, text_string):
    """Converts a string to ASCII and sends it to a DWIN Text Display address."""
    text_bytes = list(text_string.encode('ascii'))
    frame_length = 1 + 2 + len(text_bytes)

    addr_h = (address >> 8) & 0xFF
    addr_l = address & 0xFF

    frame = [0x5A, 0xA5, frame_length, 0x82, addr_h, addr_l]
    frame.extend(text_bytes)

    dwin_port.write(bytearray(frame))
    time.sleep(0.05)


def change_dwin_page(page_number):
    """Forces the DWIN display to switch to a specific page number."""
    addr_h = 0x00
    addr_l = 0x84
    password_h = 0x5A
    password_l = 0x01

    page_h = (page_number >> 8) & 0xFF
    page_l = page_number & 0xFF

    frame = [0x5A, 0xA5, 0x07, 0x82, addr_h, addr_l, password_h, password_l, page_h, page_l]
    dwin_port.write(bytearray(frame))
    time.sleep(0.05)


# --- MAIN PROGRAM EXECUTION ---

try:
    # 1. Change to the main interface page (e.g., Page 1)
    print("Switching to Page 1...")
    change_dwin_page(1)
    time.sleep(0.5)

    # 2. Define the variables to send
    bottle_amount = 12
    can_amount = 5
    total_point = 850
    user_name = "Muhammad Yusuf Pratama "  # Extra space added to clear old text

    # 3. Send the data to the display
    print("Sending variables to DWIN...")
    send_data(0x1000, bottle_amount)
    send_data(0x1001, can_amount)
    send_data(0x1002, total_point)
    send_text(0x3000, user_name)

    print("Data sent. Waiting for 'Selesai' button press...")

    # 4. Listen for the button press from DWIN
    while True:
        if dwin_port.in_waiting >= 9:
            incoming_bytes = dwin_port.read(9)
            frame = list(incoming_bytes)

            # Verify Header and Read Command
            if frame[0] == 0x5A and frame[1] == 0xA5 and frame[3] == 0x83:

                recv_address = (frame[4] << 8) | frame[5]
                recv_value = (frame[7] << 8) | frame[8]

                # Check if the incoming data is from the 'Selesai' Button (Address 0x2000)
                if recv_address == 0x2000 and recv_value == 1:
                    print("Selesai button was PRESSED!")

                    # Example action: Switch to a "Thank You" page (Page 2)
                    change_dwin_page(2)

                    # Exit the loop since we are done
                    break

        time.sleep(0.01)

except KeyboardInterrupt:
    print("\nProgram stopped by user.")
finally:
    dwin_port.close()
    print("Serial port closed.")