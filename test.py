#!/usr/bin/env python3
"""Hardware test: IR sensor + servo + buzzer (no Firebase needed).

Wiring (BCM numbering):
  - GPIO 17: IR obstacle sensor (OUT pin; most modules are active LOW)
  - GPIO 18: servo signal (SG90-style, 50Hz PWM)
  - GPIO 23: buzzer (active buzzer: HIGH = on)

Behavior:
  - IR detects an object  -> servo swings to OPEN_ANGLE, buzzer on
  - IR detects nothing    -> servo returns to REST_ANGLE, buzzer off

Run on the Pi:  python3 test.py   (stop with Ctrl+C)
"""

import time

import RPi.GPIO as GPIO

IR_PIN = 17
SERVO_PIN = 18
BUZZER_PIN = 23

REST_ANGLE = 0      # servo position when idle
OPEN_ANGLE = 90     # servo position when the IR sensor detects something

SERVO_FREQ_HZ = 50
POLL_INTERVAL_S = 0.05


def angle_to_duty(angle: float) -> float:
    """Maps 0-180 degrees to a 2.5-12.5% duty cycle (1-2ms pulse @ 50Hz)."""
    return 2.5 + (angle / 180.0) * 10.0


def set_angle(servo: GPIO.PWM, angle: float):
    servo.ChangeDutyCycle(angle_to_duty(angle))
    time.sleep(0.3)          # give the servo time to reach the position
    servo.ChangeDutyCycle(0)  # stop sending pulses to avoid jitter


def main():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(IR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(SERVO_PIN, GPIO.OUT)
    GPIO.setup(BUZZER_PIN, GPIO.OUT, initial=GPIO.LOW)

    servo = GPIO.PWM(SERVO_PIN, SERVO_FREQ_HZ)
    servo.start(0)
    set_angle(servo, REST_ANGLE)

    detected_before = False
    print("Test ready. IR -> servo + buzzer. Press Ctrl+C to stop.")

    try:
        while True:
            # most IR obstacle modules pull the OUT pin LOW on detection
            detected = GPIO.input(IR_PIN) == GPIO.LOW

            if detected and not detected_before:
                print("IR: object detected -> servo open, buzzer ON")
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
        GPIO.cleanup()
        print("GPIO cleaned up. Bye!")


if __name__ == "__main__":
    main()
