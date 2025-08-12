"""
Generate sample input images for the Center Circle task.

Creates three PNG images of different sizes in the `input/` folder.
Optionally overlays a faint crosshair at the true center to aid manual visual checks.
"""
import os
from PIL import Image, ImageDraw
import numpy as np

def create_image(path: str, width: int, height: int, color: str = "#ffffff", crosshair: bool = True) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img = Image.new("RGB", (width, height), color)
    if crosshair:
        draw = ImageDraw.Draw(img)
        cx, cy = width // 2, height // 2
        # faint crosshair
        cross_color = (200, 200, 200)
        draw.line([(cx - width, cy), (cx + width, cy)], fill=cross_color, width=1)
        draw.line([(cx, cy - height), (cx, cy + height)], fill=cross_color, width=1)
    img.save(path, format="PNG")


def main() -> None:
    task_dir = os.path.dirname(os.path.abspath(__file__))
    input_dir = os.path.join(task_dir, "input")
    width = np.random.randint(50, 500, size=3) * 2
    height = np.random.randint(50, 500, size=3) * 2
    create_image(os.path.join(input_dir, "image_1.png"), width[0], height[0])
    create_image(os.path.join(input_dir, "image_2.png"), width[1], height[1])
    create_image(os.path.join(input_dir, "image_3.png"), width[2], height[2])
    print(f"Wrote sample images to: {input_dir}")


if __name__ == "__main__":
    main() 