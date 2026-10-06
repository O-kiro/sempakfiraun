#!/usr/bin/env python3
"""Hardware test: single HC-SR04 ultrasonic sensor only.

No camera, no classifier, no servo needed for this test — just verifies
wiring and lets you calibrate BIN_FULL_DISTANCE_CM by watching live
distance readings while you move your hand / trash toward the sensor.

Wiring (BCM numbering):
  - GPIO 27: HC-SR04 TRIG
  - GPIO 22: HC-SR04 ECHO   (use a voltage divider! ECHO is 5V, Pi GPIO is 3.3V)

Run on the Pi:  python3 test_ultrasonic.py   (stop with Ctrl+C)
"""

import time

import RPi.GPIO as GPIO

TRIG_PIN = 27
ECHO_PIN = 22

ULTRASONIC_TIMEOUT_S = 0.03  # ~5m max range
READ_INTERVAL_S = 0.3


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
            return float("inf")

    pulse_end = pulse_start
    while GPIO.input(echo_pin) == GPIO.HIGH:
        pulse_end = time.monotonic()
        if pulse_end - pulse_start > ULTRASONIC_TIMEOUT_S:
            return float("inf")

    pulse_duration = pulse_end - pulse_start
    return pulse_duration * 17150  # speed of sound, round trip


def main():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(TRIG_PIN, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(ECHO_PIN, GPIO.IN)

    print("Settling sensor...")
    time.sleep(0.5)
    print("Reading distance. Move your hand toward/away from the sensor. Ctrl+C to stop.\n")

    try:
        while True:
            distance = measure_distance_cm(TRIG_PIN, ECHO_PIN)
            if distance == float("inf"):
                print("  no echo (out of range / check wiring)")
            else:
                print(f"  distance: {distance:6.1f} cm")
            time.sleep(READ_INTERVAL_S)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        GPIO.cleanup()
        print("GPIO cleaned up. Bye!")


if __name__ == "__main__":
    main()