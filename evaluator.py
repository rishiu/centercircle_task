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
	for each input image. We evaluate how close the predicted point is to the ground-truth
	target point (a crosshair intersection). If ground truth is not provided, we fall back
	to using the image center to preserve legacy behavior.

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
		# New fixed pixel tolerance (defaults to 15px). Backwards-compatible with center_tolerance_pixels.
		self.pixel_tolerance = float(criteria.get("pixel_tolerance", criteria.get("center_tolerance_pixels", 15)))
		# Relative tolerance no longer used for correctness, kept for metrics compatibility only
		self.center_tolerance_relative = float(criteria.get("center_tolerance_relative", 0.0))
		self.require_all_correct = criteria.get("require_all_correct", True)
		self.print_task_info()

	def _load_ground_truth(self, input_dir: str) -> Dict[str, Dict[str, float]]:
		"""Load ground truth target points if a ground truth file is specified in config.
		Returns mapping: image filename -> {"x": float, "y": float}
		"""
		gt_map: Dict[str, Dict[str, float]] = {}
		gt_file = self.config.get("expected_outputs", {}).get("ground_truth_file")
		if not gt_file:
			return gt_map
		gt_path = os.path.join(input_dir, gt_file)
		if not os.path.exists(gt_path):
			return gt_map
		try:
			with open(gt_path, "r") as f:
				data = json.load(f)
			targets = data.get("targets", []) if isinstance(data, dict) else []
			for t in targets:
				img = str(t.get("image", "")).strip()
				x = float(t.get("x"))
				y = float(t.get("y"))
				if img:
					gt_map[img] = {"x": x, "y": y}
		except Exception:
			# If anything goes wrong, silently fall back to center-based evaluation
			return {}
		return gt_map

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

			# Load ground truth target points if available
			gt_map = self._load_ground_truth(input_dir)

			missing_predictions: List[str] = []

			for filename in input_files:
				image_path = os.path.join(input_dir, filename)
				if not os.path.exists(image_path):
					# If inputs are missing on disk, count as error
					per_image_errors[filename] = float("inf")
					continue

				# Load image to get dimensions (for tolerance scaling)
				with Image.open(image_path) as img:
					width, height = img.size

				# Determine true target point: ground truth if provided, else image center
				if filename in gt_map:
					true_cx = gt_map[filename]["x"]
					true_cy = gt_map[filename]["y"]
				else:
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

				# Fixed 15-pixel tolerance (or value provided via pixel_tolerance)
				tol = float(self.pixel_tolerance)
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
				"tolerance_pixels": float(self.pixel_tolerance),
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