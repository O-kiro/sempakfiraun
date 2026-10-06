#!/usr/bin/env python3
"""Converts a float32 model.tflite into a faster INT8 model_int8.tflite.

Run on a LAPTOP (not the Pi), after every retrain. Calibrates with the exact
preprocessing the Pi uses in cls2.py (plain resize to the model size, /255),
then checks the INT8 model against the float model on held-out photos.

Setup (Python 3.10+, separate venv recommended):
    pip install "ai-edge-quantizer>=0.6.0" "ai-edge-litert>=2.1.4" pillow numpy

Usage:
    python3 quantize_int8.py --dataset ~/Documents/dataset
      (dataset/ must have train/<class>/ and val/<class>/ photo folders)

Then copy model_int8.tflite to the Pi and switch to it with
TRASHPOINT_MODEL=/home/pi/model_int8.tflite (see README_YOLO.md).
"""

import argparse
import glob
import os
import random

import numpy as np
from ai_edge_quantizer import qtyping, quantizer, recipe
from PIL import Image

from cls2 import TrashClassifier

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CALIB_PER_CLASS = 100
MIN_CONFIDENCE = 0.6  # same threshold main.py uses


def photos(folder: str):
    return sorted(
        p for p in glob.glob(os.path.join(folder, "*"))
        if p.lower().endswith((".jpg", ".jpeg", ".png"))
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, help="folder with train/ and val/")
    parser.add_argument("--src", default=os.path.join(BASE_DIR, "model.tflite"))
    parser.add_argument("--dst", default=os.path.join(BASE_DIR, "model_int8.tflite"))
    args = parser.parse_args()

    float_clf = TrashClassifier(model_path=args.src)
    width, height = float_clf.input_size
    input_name = float_clf.input_detail["name"].replace("serving_default_", "").split(":")[0]

    def prep(path):
        x = np.asarray(Image.open(path).convert("RGB").resize((width, height)), dtype=np.float32) / 255.0
        if float_clf.channels_first:
            x = np.transpose(x, (2, 0, 1))
        return x[None]

    # 1) calibrate on a balanced random sample of TRAIN photos
    random.seed(0)
    calib = []
    for label in float_clf.labels:
        files = photos(os.path.join(args.dataset, "train", label))
        calib += random.sample(files, min(CALIB_PER_CLASS, len(files)))
    print(f"Calibrating on {len(calib)} train photos...")

    qt = quantizer.Quantizer(args.src)
    qt.load_quantization_recipe(recipe.static_wi8_ai8())
    # keep float32 input/output so cls2.py works unchanged
    for op in (qtyping.TFLOperationName.INPUT, qtyping.TFLOperationName.OUTPUT):
        qt.update_quantization_recipe(
            regex=".*", operation_name=op, algorithm_key=recipe.AlgorithmName.NO_QUANTIZE
        )
    result = qt.calibrate({"serving_default": [{input_name: prep(p)} for p in calib]})
    qt.quantize(calibration_result=result).export_model(args.dst, overwrite=True)
    print(f"Saved {args.dst} ({os.path.getsize(args.dst) / 1e6:.1f} MB, "
          f"float was {os.path.getsize(args.src) / 1e6:.1f} MB)")

    # 2) compare float vs INT8 on held-out VAL photos
    int8_clf = TrashClassifier(model_path=args.dst)
    total = same = float_ok = int8_ok = 0
    for label in float_clf.labels:
        for path in photos(os.path.join(args.dataset, "val", label)):
            rgb = np.asarray(Image.open(path).convert("RGB"))
            f_label, f_conf = float_clf.classify_array(rgb)
            i_label, i_conf = int8_clf.classify_array(rgb)
            total += 1
            same += f_label == i_label
            float_ok += f_label == label and f_conf >= MIN_CONFIDENCE
            int8_ok += i_label == label and i_conf >= MIN_CONFIDENCE
    print(f"Val photos: {total}")
    print(f"  same label float vs INT8 : {same}/{total}")
    print(f"  accepted & correct float : {float_ok / total:.1%}")
    print(f"  accepted & correct INT8  : {int8_ok / total:.1%}")
    if int8_ok < float_ok:
        print("  WARNING: INT8 is less accurate on this data — test carefully before switching")


if __name__ == "__main__":
    main()
