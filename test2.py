#!/usr/bin/env python3
"""Hardware test 2: IR sensor + camera + servo + buzzer (no Firebase needed).

Wiring (BCM numbering) — same pins as test.py:
  - GPIO 17: IR obstacle sensor (OUT pin; most modules are active LOW)
  - GPIO 18: servo signal (SG90-style, 50Hz PWM)
  - GPIO 23: buzzer (active buzzer: HIGH = on)
  - OV5647 camera on the CSI ribbon (picamera2)

Behavior:
  - IR detects an object -> camera snaps a photo to captures/,
    THEN servo swings to OPEN_ANGLE while the buzzer beeps (together)
  - IR clear            -> servo returns to REST_ANGLE, buzzer off

Run on the Pi:  python3 test2.py   (stop with Ctrl+C)
"""

import os
import time

import RPi.GPIO as GPIO
from picamera2 import Picamera2

IR_PIN = 17
SERVO_PIN = 18
BUZZER_PIN = 23

REST_ANGLE = 0      # servo position when idle
OPEN_ANGLE = 90     # servo position when the IR sensor detects something

SERVO_FREQ_HZ = 50
POLL_INTERVAL_S = 0.05

CAPTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "captures")


def angle_to_duty(angle: float) -> float:
    """Maps 0-180 degrees to a 2.5-12.5% duty cycle (1-2ms pulse @ 50Hz)."""
    return 2.5 + (angle / 180.0) * 10.0


def set_angle(servo: GPIO.PWM, angle: float):
    servo.ChangeDutyCycle(angle_to_duty(angle))
    time.sleep(0.3)          # give the servo time to reach the position
    servo.ChangeDutyCycle(0)  # stop sending pulses to avoid jitter


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
    path = os.path.join(CAPTURES_DIR, f"test-{timestamp}.jpg")
    camera.capture_file(path)
    return path


def main():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(IR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(SERVO_PIN, GPIO.OUT)
    GPIO.setup(BUZZER_PIN, GPIO.OUT, initial=GPIO.LOW)

    servo = GPIO.PWM(SERVO_PIN, SERVO_FREQ_HZ)
    servo.start(0)
    set_angle(servo, REST_ANGLE)

    print("Starting camera...")
    camera = setup_camera()

    detected_before = False
    print("Test ready. IR -> photo -> servo + buzzer. Press Ctrl+C to stop.")

    try:
        while True:
            # most IR obstacle modules pull the OUT pin LOW on detection
            detected = GPIO.input(IR_PIN) == GPIO.LOW

            if detected and not detected_before:
                print("IR: object detected -> taking photo...")
                photo_path = take_photo(camera)
                print(f"Photo saved: {photo_path}")

                # servo and buzzer together: buzzer starts right before the
                # servo pulse so they fire at (effectively) the same moment
                print("Servo open + buzzer ON")
                GPIO.output(BUZZER_PIN, GPIO.HIGH)
                set_angle(servo, OPEN_ANGLE)
            elif not detected and detected_before:
                print("IR: clear -> servo rest, buzzer OFF")
                GPIO.output(BUZZER_PIN, GPIO.LOW)
                set_angle(servo, REST_ANGLE)

            detected_before = detected
            time.sleep(POLL_INTERVAL_S)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        GPIO.output(BUZZER_PIN, GPIO.LOW)
        set_angle(servo, REST_ANGLE)
        servo.stop()
        camera.stop()
        camera.close()
        GPIO.cleanup()
        print("GPIO cleaned up. Bye!")


if __name__ == "__main__":
    main()
