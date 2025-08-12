from typing import Any, Dict, List
import os
import json
import time
from datetime import datetime
from PIL import Image
from math import hypot

from benchmark.core.base_evaluator import BaseEvaluator
from benchmark.core.result_types import EvaluationResult


class CenterCircleEvaluator(BaseEvaluator):
    """
    Evaluator for the Center Circle task.

    The agent must output a JSON file with predicted circle centers (and optional radius)
    for each input image. We evaluate how close the predicted center is to the true image center.

    Expected output file (config.expected_outputs.solution_file), JSON format:
    {
      "circles": [
        {"image": "image_1.png", "x": 160, "y": 120, "radius": 50},
        {"image": "image_2.png", "x": 320, "y": 240, "radius": 60}
      ]
    }
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        criteria = config.get("evaluation_criteria", {})
        # Pixel tolerance and relative tolerance; we accept if error <= max(abs, rel*min_dim)
        self.center_tolerance_pixels = criteria.get("center_tolerance_pixels", 3)
        self.center_tolerance_relative = criteria.get("center_tolerance_relative", 0.02)
        self.require_all_correct = criteria.get("require_all_correct", True)
        self.print_task_info()

    def evaluate(self, solution_folder: str, solution_config: Any = None) -> EvaluationResult:
        start_time = time.time()
        task_id = self.config.get("task_id", "center_circle")

        try:
            # Resolve expected outputs and input files
            solution_file_name = self.config["expected_outputs"]["solution_file"]
            solution_path = os.path.join(solution_folder, solution_file_name)
            input_files: List[str] = self.config.get("input_files", [])

            if not os.path.exists(solution_path):
                return EvaluationResult(
                    task_id=task_id,
                    agent_id="unknown",
                    timestamp=datetime.now(),
                    metrics={},
                    success=False,
                    execution_time=time.time() - start_time,
                    error_message=f"Solution file not found: {solution_path}",
                    artifacts={},
                )

            with open(solution_path, "r") as f:
                data = json.load(f)

            if not isinstance(data, dict) or "circles" not in data:
                return EvaluationResult(
                    task_id=task_id,
                    agent_id="unknown",
                    timestamp=datetime.now(),
                    metrics={},
                    success=False,
                    execution_time=time.time() - start_time,
                    error_message="Invalid solution format. Expected a JSON object with key 'circles'",
                    artifacts={},
                )

            predictions = data.get("circles", [])
            if not isinstance(predictions, list):
                return EvaluationResult(
                    task_id=task_id,
                    agent_id="unknown",
                    timestamp=datetime.now(),
                    metrics={},
                    success=False,
                    execution_time=time.time() - start_time,
                    error_message="'circles' must be a list of objects with keys: image, x, y, [radius]",
                    artifacts={},
                )

            # Build lookup for predictions by filename
            pred_by_image: Dict[str, Dict[str, float]] = {}
            for pred in predictions:
                try:
                    img_name = str(pred["image"]).strip()
                    x = float(pred["x"])  # allow float; will evaluate in pixels
                    y = float(pred["y"])  # allow float; will evaluate in pixels
                    radius = float(pred.get("radius", 0.0))
                    pred_by_image[img_name] = {"x": x, "y": y, "radius": radius}
                except Exception:
                    # Skip invalid entries
                    continue

            # Evaluate each input image
            per_image_errors: Dict[str, float] = {}
            num_correct = 0
            max_error = 0.0
            total_error = 0.0
            total_images = len(input_files)

            # Input images are stored within the task's input folder
            task_dir = os.path.dirname(os.path.abspath(__file__))
            input_dir = os.path.join(task_dir, "input")

            missing_predictions: List[str] = []

            for filename in input_files:
                image_path = os.path.join(input_dir, filename)
                if not os.path.exists(image_path):
                    # If inputs are missing on disk, count as error
                    per_image_errors[filename] = float("inf")
                    continue

                # Load image to get true center
                with Image.open(image_path) as img:
                    width, height = img.size
                true_cx = width / 2.0
                true_cy = height / 2.0

                pred = pred_by_image.get(filename)
                if pred is None:
                    missing_predictions.append(filename)
                    per_image_errors[filename] = float("inf")
                    continue

                dx = pred["x"] - true_cx
                dy = pred["y"] - true_cy
                err = (dx * dx + dy * dy) ** 0.5
                per_image_errors[filename] = err

                tol = max(self.center_tolerance_pixels, self.center_tolerance_relative * min(width, height))
                is_correct = err <= tol
                if is_correct:
                    num_correct += 1
                max_error = max(max_error, err)
                total_error += err

            avg_error = (total_error / total_images) if total_images > 0 else 0.0

            # Success logic: either all images correct, or a fraction threshold (default all)
            if self.require_all_correct:
                success = (num_correct == total_images)
            else:
                # Allow e.g., 90% correct; configurable later if needed
                success_fraction_threshold = self.config.get("evaluation_criteria", {}).get("min_fraction_correct", 0.9)
                success = (total_images == 0) or (num_correct / total_images >= success_fraction_threshold)

            metrics = {
                "num_images": float(total_images),
                "num_correct": float(num_correct),
                "avg_center_error_pixels": float(avg_error),
                "max_center_error_pixels": float(max_error),
                "tolerance_pixels": float(self.center_tolerance_pixels),
                "tolerance_relative": float(self.center_tolerance_relative),
            }

            artifacts = {
                "missing_predictions": ",".join(missing_predictions) if missing_predictions else "",
                "per_image_errors_json": json.dumps(per_image_errors),
            }

            return EvaluationResult(
                task_id=task_id,
                agent_id="unknown",
                timestamp=datetime.now(),
                metrics=metrics,
                success=success,
                execution_time=time.time() - start_time,
                error_message=None if success else "Some predictions are missing or outside tolerance.",
                artifacts=artifacts,
            )

        except Exception as e:
            return EvaluationResult(
                task_id=task_id,
                agent_id="unknown",
                timestamp=datetime.now(),
                metrics={},
                success=False,
                execution_time=time.time() - start_time,
                error_message=f"Error during evaluation: {e}",
                artifacts={},
            )

    def get_metrics(self) -> List[str]:
        return [
            "num_images",
            "num_correct",
            "avg_center_error_pixels",
            "max_center_error_pixels",
            "tolerance_pixels",
            "tolerance_relative",
        ]

    def generate_report(self, results: List[EvaluationResult]) -> str:
        lines: List[str] = []
        for res in results:
            lines.append(f"Task: {res.task_id}, Success: {res.success}, Time: {res.execution_time:.2f}s")
            if res.error_message:
                lines.append(f"  Error: {res.error_message}")
            for k, v in res.metrics.items():
                if isinstance(v, float):
                    lines.append(f"  {k}: {v:.4f}")
                else:
                    lines.append(f"  {k}: {v}")
        return "\n".join(lines) 