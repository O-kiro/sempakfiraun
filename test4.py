#!/usr/bin/env python3
"""Hardware test 3: full AI sorting flow (no Firebase needed).

Flow:
  IR detects item in chamber -> camera takes photo
  -> YOLOv8n-cls (TFLite) classifies the photo
     -> plastik : check plastik bin level ->
                    not full : 1 beep, servo tilts chamber LEFT, back to center
                    full     : 4 beeps ("bin penuh"), no tilt (item rejected)
     -> kaleng  : check kaleng bin level ->
                    not full : 2 beeps, servo tilts chamber RIGHT, back to center
                    full     : 4 beeps ("bin penuh"), no tilt (item rejected)
     -> lainnya / low confidence : 3 error beeps, no tilt (item rejected)
  -> wait until the chamber is clear, then re-arm

Wiring (BCM numbering) — same pins as test.py / test2.py, plus new ultrasonic pins:
  - GPIO 17: IR obstacle sensor in the chamber (active LOW)
  - GPIO 18: servo that tilts the chamber (SG90-style, 50Hz PWM)
  - GPIO 23: buzzer (active buzzer: HIGH = on)
  - OV5647 camera on the CSI ribbon (picamera2)

  - GPIO 27: HC-SR04 TRIG, plastik bin
  - GPIO 22: HC-SR04 ECHO, plastik bin   (use a voltage divider, ECHO is 5V!)

Mount each HC-SR04 facing straight down into its bin, at the top. Measures
the distance down to the trash pile: a SMALL distance means the bin is
nearly full (trash close to the sensor), a LARGE distance means the bin
is empty. Adjust BIN_FULL_DISTANCE_CM below to match your bin's depth.

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

# --- ultrasonic bin-level sensors (HC-SR04) ---
PLASTIK_TRIG_PIN = 27
PLASTIK_ECHO_PIN = 22

# distance (cm) from sensor to trash pile at which the bin counts as "full"
# measure your empty-bin distance and set this to ~15-20% of that
BIN_FULL_DISTANCE_CM = 8.0

# how many consecutive full readings before we trust it (debounce noise)
BIN_FULL_CONFIRM_READS = 3

# timeout for a single ultrasonic ping, in seconds
ULTRASONIC_TIMEOUT_S = 0.03  # ~5m max range, way more than needed indoors

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


def measure_distance_cm(trig_pin: int, echo_pin: int) -> float:
    """One HC-SR04 ping. Returns distance in cm, or float('inf') on timeout."""
    GPIO.output(trig_pin, GPIO.LOW)
    time.sleep(0.000002)
    GPIO.output(trig_pin, GPIO.HIGH)
    time.sleep(0.00001)  # 10us trigger pulse
    GPIO.output(trig_pin, GPIO.LOW)

    start_wait = time.monotonic()
    pulse_start = start_wait
    while GPIO.input(echo_pin) == GPIO.LOW:
        pulse_start = time.monotonic()
        if pulse_start - start_wait > ULTRASONIC_TIMEOUT_S:
            return float("inf")  # echo never went high -> treat as out of range

    pulse_end = pulse_start
    while GPIO.input(echo_pin) == GPIO.HIGH:
        pulse_end = time.monotonic()
        if pulse_end - pulse_start > ULTRASONIC_TIMEOUT_S:
            return float("inf")  # echo stuck high -> treat as out of range

    pulse_duration = pulse_end - pulse_start
    # speed of sound ~343 m/s -> 17150 cm/s one-way (divide round trip by 2)
    return pulse_duration * 17150


def is_bin_full(trig_pin: int, echo_pin: int) -> bool:
    """Debounced full-bin check: requires several consecutive close readings."""
    close_reads = 0
    for _ in range(BIN_FULL_CONFIRM_READS):
        distance = measure_distance_cm(trig_pin, echo_pin)
        if distance <= BIN_FULL_DISTANCE_CM:
            close_reads += 1
        time.sleep(0.06)  # HC-SR04 needs a short gap between pings
    return close_reads == BIN_FULL_CONFIRM_READS


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
        if is_bin_full(PLASTIK_TRIG_PIN, PLASTIK_ECHO_PIN):
            print(f"-> PLASTIK ({confidence * 100:.1f}%) : bin PENUH, item ditolak")
            beep(4)
            return
        print(f"-> PLASTIK ({confidence * 100:.1f}%) : tilt LEFT")
        beep(1)
        set_angle(servo, LEFT_ANGLE)
        time.sleep(TILT_HOLD_S)
        set_angle(servo, CENTER_ANGLE)
    elif label == "kaleng":
        if is_bin_full(KALENG_TRIG_PIN, KALENG_ECHO_PIN):
            print(f"-> KALENG ({confidence * 100:.1f}%) : bin PENUH, item ditolak")
            beep(4)
            return
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

    GPIO.setup(PLASTIK_TRIG_PIN, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(PLASTIK_ECHO_PIN, GPIO.IN)
    GPIO.setup(KALENG_TRIG_PIN, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(KALENG_ECHO_PIN, GPIO.IN)

    servo = GPIO.PWM(SERVO_PIN, SERVO_FREQ_HZ)
    servo.start(0)
    set_angle(servo, CENTER_ANGLE)

    print("Loading classifier (model.tflite)...")
    classifier = TrashClassifier()
    print(f"Classes: {classifier.labels}")

    print("Starting camera...")
    camera = setup_camera()

    print("Checking bin levels...")
    plastik_full = is_bin_full(PLASTIK_TRIG_PIN, PLASTIK_ECHO_PIN)
    print(f"  plastik bin: {'PENUH' if plastik_full else 'ok'}")

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