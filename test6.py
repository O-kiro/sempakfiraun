#!/usr/bin/env python3
"""Standalone servo test — sweeps GPIO 18 from 0 to 180 and back.

Run this directly (not via main.py) to check the servo physically
reaches full range. If it still only swings ~45°, try tweaking
MIN_DUTY / MAX_DUTY below — not all servos agree on the 2.5%-12.5%
duty cycle range for 0°-180°; cheap SG90-style ones sometimes need
different numbers (e.g. 2%-12%, or need MG90S-specific values).

Usage:
    python3 servo_test.py
"""

import time

import RPi.GPIO as GPIO

SERVO_PIN = 18
SERVO_FREQ_HZ = 50

# Calibration — adjust these if the servo doesn't reach true 0°/180°
MIN_DUTY = 2.5   # duty cycle % at 0°
MAX_DUTY = 12.5  # duty cycle % at 180°

# How long to wait per degree of movement, plus a small fixed minimum.
# A full 0->180 sweep needs noticeably more time than a small nudge —
# a single fixed sleep(0.3) is why a big move (0->180) can look like it
# only makes it partway before power gets cut.
SECONDS_PER_DEGREE = 0.006
MIN_MOVE_TIME = 0.3


def angle_to_duty(angle: float) -> float:
    angle = max(0.0, min(180.0, angle))
    return MIN_DUTY + (angle / 180.0) * (MAX_DUTY - MIN_DUTY)


def move_to(pwm, angle: float, from_angle: float = 90.0):
    duty = angle_to_duty(angle)
    pwm.ChangeDutyCycle(duty)
    distance = abs(angle - from_angle)
    wait_time = max(MIN_MOVE_TIME, distance * SECONDS_PER_DEGREE)
    time.sleep(wait_time)
    pwm.ChangeDutyCycle(0)  # stop sending pulses so servo doesn't jitter/buzz
    print(f"  -> moved to {angle:.0f}° (duty={duty:.2f}%, waited {wait_time:.2f}s)")


def main():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(SERVO_PIN, GPIO.OUT)
    pwm = GPIO.PWM(SERVO_PIN, SERVO_FREQ_HZ)
    pwm.start(0)

    try:
        print("Sweep test: 0 -> 45 -> 90 -> 135 -> 180 -> 90")
        last = 90.0
        for target in [0, 45, 90, 135, 180, 90]:
            print(f"Moving to {target}°...")
            move_to(pwm, target, from_angle=last)
            last = target
            time.sleep(0.5)  # pause so you can see/measure each position

        print("\nDone. If it visibly stopped short of 0° or 180°, adjust")
        print("MIN_DUTY / MAX_DUTY at the top of this file and re-run.")
    except KeyboardInterrupt:
        pass
    finally:
        pwm.stop()
        GPIO.cleanup()


if __name__ == "__main__":
    main()