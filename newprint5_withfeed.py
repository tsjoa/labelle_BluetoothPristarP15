#!/usr/bin/env python3
from bluepy.btle import Peripheral, BTLEDisconnectError
from PIL import Image, ImageDraw, ImageFont
from matplotlib import font_manager
import argparse
import time
import sys

SERVICE_UUID = "0000ff00-0000-1000-8000-00805f9b34fb"
CHAR_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"

def construct_bitmap(text, font_size, font_family="Arial", bold=False, italic=False, underline=False, canvas_height=96):
    """Creates a monochrome bitmap from text."""
    try:
        font_path = font_manager.findfont(font_manager.FontProperties(
            family=font_family,
            weight="bold" if bold else "normal",
            style="italic" if italic else "normal"
        ))
        font = ImageFont.truetype(font_path, font_size)
    except Exception:
        try:
            font = ImageFont.truetype(f"{font_family}.ttf", font_size)
        except IOError:
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except IOError:
                font = ImageFont.load_default()

    dummy_img = Image.new('1', (1, 1))
    draw = ImageDraw.Draw(dummy_img)
    text_width = draw.textlength(text, font=font)
    canvas_width = int(text_width) + 4

    img = Image.new('1', (canvas_width, canvas_height), color=1)
    draw = ImageDraw.Draw(img)
    draw.text((2, canvas_height / 2), text, font=font, fill=0, anchor="lm")

    if underline:
        text_height = font.getbbox(text)[3]
        underline_y = (canvas_height / 2) + (text_height / 2)
        draw.line([(2, underline_y), (text_width + 2, underline_y)], fill=0, width=1)

    return img

def bitmap_to_packet(bitmap):
    """Converts a PIL image to the printer's packet format."""
    width, height = bitmap.size
    bytes_ = []
    for x in range(width):
        for y_byte_group in range(height - 8, -1, -8):
            byte = 0
            for bit in range(8):
                px_y = y_byte_group + bit
                if 0 <= px_y < height and bitmap.getpixel((x, px_y)) == 0:
                    byte |= (1 << bit)
            bytes_.append(byte)
    return bytes(bytes_)

def connect_to_printer(device_address, retries=5, delay=2):
    """Connects to the printer via BLE (bluepy)."""
    for i in range(retries):
        try:
            print(f"Connecting to {device_address} (attempt {i+1}/{retries})...")
            peripheral = Peripheral(device_address)
            peripheral.setMTU(100)
            print(f"Connected to {device_address}")
            return peripheral
        except BTLEDisconnectError as e:
            print(f"Connection attempt {i+1}/{retries} failed: {e}")
            if i < retries - 1:
                time.sleep(delay)
            else:
                print("Could not connect. Make sure the printer is in BLE mode (blue light).")
                return None
        except Exception as e:
            print(f"Unexpected error: {e}")
            time.sleep(delay)
    return None


def send_print_job(peripheral, bitmap, segmented_paper=False):
    """Sends the print job to a connected printer with proper paper advance."""
    payload = bitmap_to_packet(bitmap)
    canvas_width = bitmap.width

    try:
        char = peripheral.getCharacteristics(uuid=CHAR_UUID)[0]

        # Build packets
        packets = [
            bytes([0x10, 0xff, 0x40]),  # init command
            bytes([
                *([0x00] * 15),
                0x10, 0xff, 0xf1, 0x02, 0x1d,
                0x76,
                0x30, 0x00,
                0x0c, 0x00,
                canvas_width & 0xff, (canvas_width >> 8) & 0xff
            ]),
            payload,
        ]

        # Add line feeds to advance paper
        packets.append(bytes([0x0a] * 5))  # feed 5 lines

        if segmented_paper:
            packets.extend([
                bytes([0x1d, 0x0c, 0x10]),
                bytes([0xff, 0xf1, 0x45]),
                bytes([0x10, 0xff, 0x40]),
                bytes([0x10, 0xff, 0x40]),
            ])
        else:
            packets.extend([
                bytes([0x10, 0xff, 0xf1, 0x45])
            ])

        # Send packets in chunks
        for p in packets:
            chunks = [p[i:i + 96] for i in range(0, len(p), 96)]
            for chunk in chunks:
                char.write(chunk, withResponse=False)
                time.sleep(0.03)

        print("Print successful!")
        return True
    except Exception as e:
        print(f"Print error: {e}")
        return False



def main():
    parser = argparse.ArgumentParser(description="Interactive BLE thermal printer using bluepy.")
    parser.add_argument("--font-size", type=int, default=72)
    parser.add_argument("--font-family", type=str, default="Arial")
    parser.add_argument("--bold", action="store_true")
    parser.add_argument("--italic", action="store_true")
    parser.add_argument("--underline", action="store_true")
    parser.add_argument("--segmented-paper", action="store_true")
    args = parser.parse_args()

    device_address = "03:0D:7A:D6:5E:B1"

    peripheral = connect_to_printer(device_address)
    if peripheral is None:
        sys.exit(1)

    print("\nPrinter ready. Enter text to print (Ctrl+C to exit).")
    try:
        while True:
            text_to_print = input("Enter text: ")
            if peripheral is None:
                print("Printer disconnected. Attempting to reconnect...")
                peripheral = connect_to_printer(device_address)
                if peripheral is None:
                    print("Reconnection failed. Exiting.")
                    break
            bitmap = construct_bitmap(
                text_to_print,
                args.font_size,
                args.font_family,
                args.bold,
                args.italic,
                args.underline
            )
            try:
                send_print_job(peripheral, bitmap, args.segmented_paper)
            except BTLEDisconnectError:
                print("Printer disconnected unexpectedly.")
                peripheral = None

    except KeyboardInterrupt:
        print("\nDisconnecting from printer...")
    finally:
        try:
            peripheral.disconnect()
        except Exception:
            pass
        print("Disconnected.")

if __name__ == "__main__":
    main()