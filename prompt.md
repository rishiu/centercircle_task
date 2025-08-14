Task: Match the crosshair target point in each input image

You are given several 512x512 input images in the `input/` directory of this task. Each image contains a visible crosshair (a horizontal and vertical line) that intersect at a random target point. Your goal is to produce a JSON file named `solution.json` in your workspace that specifies, for each input image, the x and y pixel coordinates of a circle center and an arbitrary radius. The circle center should match the crosshair intersection point as precisely as possible. 

You may generate provisional overlay images to visualize your current guess and update until your circle center visibly aligns with the crosshair intersection. Only the final JSON is required for grading. 

Input images:
- `image_1.png`
- `image_2.png`
- `image_3.png`

Expected output format (solution.json):
{
  "circles": [
    {"image": "image_1.png", "x": <float>, "y": <float>, "radius": <float>},
    {"image": "image_2.png", "x": <float>, "y": <float>, "radius": <float>},
    {"image": "image_3.png", "x": <float>, "y": <float>, "radius": <float>}
  ]
}

Notes:
- Your radius choice does not affect scoring; only the center coordinates do.
- Success is achieved when your predicted center for every image is within a small tolerance of the true target point.