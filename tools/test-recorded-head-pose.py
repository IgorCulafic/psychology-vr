"""Check camera/character handedness, calibration, and missing-pose behavior."""
import importlib.util
from pathlib import Path
import unittest
import cv2
import numpy as np

spec = importlib.util.spec_from_file_location("extract", Path(__file__).with_name("extract-livelink-video.py"))
extract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extract)


class HeadPoseTests(unittest.TestCase):
    def test_visible_nod_turn_and_tilt_directions(self):
        # Positive camera X nods down; camera Y turns toward screen right;
        # camera Z tilts the top of the head toward screen left.
        for axis, expected_sign in [(0, 1), (1, -1), (2, -1)]:
            rvec = np.zeros(3)
            rvec[axis] = np.radians(20)
            rotation = cv2.Rodrigues(rvec)[0]
            result = extract.head_rotations([np.eye(3)] * 3 + [rotation] * 3)
            self.assertAlmostEqual(result[-1][axis], expected_sign * np.sin(np.radians(10)), places=6)
            self.assertAlmostEqual(result[-1][3], np.cos(np.radians(10)), places=6)

    def test_initial_camera_angle_is_removed(self):
        rest = cv2.Rodrigues(np.array([.1, -.2, .3]))[0]
        result = extract.head_rotations([None, rest, rest, rest])
        np.testing.assert_allclose(result, [[0, 0, 0, 1]] * 4, atol=1e-6)

    def test_matrices_produce_normalized_continuous_quaternions(self):
        result = extract.head_rotations([cv2.Rodrigues(np.array([0., 0., a]))[0] * 1.02 for a in np.linspace(0, 4, 100)])
        np.testing.assert_allclose(np.linalg.norm(result, axis=1), 1, atol=1e-6)
        self.assertTrue(all(np.dot(a, b) >= 0 for a, b in zip(result, result[1:])))

    def test_missing_pose_is_explicit_rest(self):
        result = extract.head_rotations([np.eye(3), None, np.eye(3)])
        np.testing.assert_allclose(result[1], [0, 0, 0, 1])


if __name__ == "__main__":
    unittest.main()
