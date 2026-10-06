#!/usr/bin/env python3
"""Hardware test 3: full AI sorting flow (no Firebase needed).

Flow:
  IR detects item in chamber -> camera takes photo
  -> YOLOv8n-cls (TFLite) classifies the photo
     -> plastik : 1 beep, servo tilts chamber LEFT, back to center
     -> kaleng  : 2 beeps, servo tilts chamber RIGHT, back to center
     -> lainnya / low confidence : 3 error beeps, no tilt (item rejected)
  -> wait until the chamber is clear, then re-arm

Wiring (BCM numbering) — same pins as test.py / test2.py:
  - GPIO 17: IR obstacle sensor in the chamber (active LOW)
  - GPIO 18: servo that tilts the chamber (SG90-style, 50Hz PWM)
  - GPIO 23: buzzer (active buzzer: HIGH = on)
  - OV5647 camera on the CSI ribbon (picamera2)

Needs model.tflite + labels.txt next to this script (see README_YOLO.md).

Run on the Pi:  python3 test3.py   (stop with Ctrl+C)
"""

import os
import time

import RPi.GPIO as GPIO
from picamera2 import Picamera2

from classifier import TrashClassifier

IR_PIN = 17
SERVO_PIN = 18
BUZZER_PIN = 23

# chamber tilt angles — adjust to your mechanics
CENTER_ANGLE = 90
LEFT_ANGLE = 30     # plastik side
RIGHT_ANGLE = 150   # kaleng side
TILT_HOLD_S = 1.2   # how long the chamber stays tilted so the item slides out

CONFIDENCE_THRESHOLD = 0.60  # below this -> treat as "lainnya" (reject)

SERVO_FREQ_HZ = 50
POLL_INTERVAL_S = 0.05

CAPTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "captures")


def angle_to_duty(angle: float) -> float:
    """Maps 0-180 degrees to a 2.5-12.5% duty cycle (1-2ms pulse @ 50Hz)."""
    return 2.5 + (angle / 180.0) * 10.0


def set_angle(servo: GPIO.PWM, angle: float):
    servo.ChangeDutyCycle(angle_to_duty(angle))
    time.sleep(0.4)           # give the servo time to reach the position
    servo.ChangeDutyCycle(0)  # stop sending pulses to avoid jitter


def beep(times: int, on_s: float = 0.12):
    for _ in range(times):
        GPIO.output(BUZZER_PIN, GPIO.HIGH)
        time.sleep(on_s)
        GPIO.output(BUZZER_PIN, GPIO.LOW)
        time.sleep(0.08)


def setup_camera() -> Picamera2:
    os.makedirs(CAPTURES_DIR, exist_ok=True)
    camera = Picamera2()
    config = camera.create_still_configuration(main={"size": (1296, 972)})
    camera.configure(config)
    camera.start()
    time.sleep(1.0)  # let auto-exposure settle
    return camera


def take_photo(camera: Picamera2) -> str:
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    path = os.path.join(CAPTURES_DIR, f"sort-{timestamp}.jpg")
    camera.capture_file(path)
    return path


def sort_item(servo: GPIO.PWM, label: str, confidence: float):
    if confidence < CONFIDENCE_THRESHOLD:
        label = "lainnya"

    if label == "plastik":
        print(f"-> PLASTIK ({confidence * 100:.1f}%) : tilt LEFT")
        beep(1)
        set_angle(servo, LEFT_ANGLE)
        time.sleep(TILT_HOLD_S)
        set_angle(servo, CENTER_ANGLE)
    elif label == "kaleng":
        print(f"-> KALENG ({confidence * 100:.1f}%) : tilt RIGHT")
        beep(2)
        set_angle(servo, RIGHT_ANGLE)
        time.sleep(TILT_HOLD_S)
        set_angle(servo, CENTER_ANGLE)
    else:
        print(f"-> DITOLAK ({label}, {confidence * 100:.1f}%) : no tilt")
        beep(3)


def main():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(IR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(SERVO_PIN, GPIO.OUT)
    GPIO.setup(BUZZER_PIN, GPIO.OUT, initial=GPIO.LOW)

    servo = GPIO.PWM(SERVO_PIN, SERVO_FREQ_HZ)
    servo.start(0)
    set_angle(servo, CENTER_ANGLE)

    print("Loading classifier (model.tflite)...")
    classifier = TrashClassifier()
    print(f"Classes: {classifier.labels}")

    print("Starting camera...")
    camera = setup_camera()

    print("Sorting test ready. Drop an item in the chamber. Ctrl+C to stop.")

    try:
        while True:
            # most IR obstacle modules pull the OUT pin LOW on detection
            if GPIO.input(IR_PIN) == GPIO.LOW:
                # small debounce: make sure the item has settled
                time.sleep(0.3)
                if GPIO.input(IR_PIN) != GPIO.LOW:
                    continue

                print("IR: item in chamber -> taking photo...")
                photo_path = take_photo(camera)
                print(f"Photo saved: {photo_path}")

                start = time.monotonic()
                label, confidence = classifier.classify(photo_path)
                elapsed = time.monotonic() - start
                print(f"Classified in {elapsed:.2f}s: {label} ({confidence * 100:.1f}%)")

                sort_item(servo, label, confidence)

                # wait until the chamber is clear before re-arming
                print("Waiting for chamber to clear...")
                while GPIO.input(IR_PIN) == GPIO.LOW:
                    time.sleep(POLL_INTERVAL_S)
                time.sleep(0.5)
                print("Ready for the next item.\n")

            time.sleep(POLL_INTERVAL_S)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        GPIO.output(BUZZER_PIN, GPIO.LOW)
        set_angle(servo, CENTER_ANGLE)
        servo.stop()
        camera.stop()
        camera.close()
        GPIO.cleanup()
        print("GPIO cleaned up. Bye!")


if __name__ == "__main__":
    main()
