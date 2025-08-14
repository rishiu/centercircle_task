"""
Generate sample input images for the Center Circle task.

Creates three 512x512 PNG images in the `input/` folder.
Draws a full-length horizontal and vertical line that intersect at a random target point per image.
Writes ground truth target coordinates to `targets.json` in the same folder.
Also generates ground-truth overlays ("*_gt.png") with a red circle at the target point.
"""
import os
import json
import random
from typing import List, Dict
from PIL import Image, ImageDraw


def create_image_with_target(path: str, width: int, height: int, target_x: int, target_y: int, color: str = "#ffffff") -> None:
	os.makedirs(os.path.dirname(path), exist_ok=True)
	img = Image.new("RGB", (width, height), color)
	draw = ImageDraw.Draw(img)
	cross_color = (200, 200, 200)
	# Horizontal line at y = target_y, vertical line at x = target_x (full length)
	draw.line([(0, target_y), (width, target_y)], fill=cross_color, width=1)
	draw.line([(target_x, 0), (target_x, height)], fill=cross_color, width=1)
	img.save(path, format="PNG")


def save_gt_overlay(base_path: str, target_x: int, target_y: int, radius: int = 10) -> None:
	"""Create a copy of the base image with a red circle centered at the target for visualization."""
	# Load base image
	img = Image.open(base_path).convert("RGB")
	draw = ImageDraw.Draw(img)
	# Red circle
	bbox = [
		(target_x - radius, target_y - radius),
		(target_x + radius, target_y + radius),
	]
	draw.ellipse(bbox, outline=(255, 0, 0), width=3)
	root, ext = os.path.splitext(base_path)
	img.save(f"{root}_gt{ext}", format="PNG")


def main() -> None:
	task_dir = os.path.dirname(os.path.abspath(__file__))
	input_dir = os.path.join(task_dir, "input")
	width, height = 512, 512
	files = ["image_1.png", "image_2.png", "image_3.png"]
	gt: List[Dict[str, int]] = []
	for fname in files:
		# keep a small margin so the crosshair is visible across the canvas
		tx = random.randint(8, width - 8)
		ty = random.randint(8, height - 8)
		img_path = os.path.join(input_dir, fname)
		create_image_with_target(img_path, width, height, tx, ty)
		save_gt_overlay(img_path, tx, ty, radius=10)
		gt.append({"image": fname, "x": tx, "y": ty})

	# Write ground truth
	with open(os.path.join(input_dir, "targets.json"), "w") as f:
		json.dump({"targets": gt}, f)
	print(f"Wrote sample images and ground truth to: {input_dir}")


if __name__ == "__main__":
	main() 