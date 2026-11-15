import unittest
from tracking.motion import Settings, Motion, map_axis


class MotionTests(unittest.TestCase):
    def test_center_and_edges_with_reversal(self):
        self.assertEqual(map_axis(0.5,45,135,False,0.04),90)
        self.assertEqual(map_axis(-1,45,135,False,0.04),45)
        self.assertEqual(map_axis(2,45,135,False,0.04),135)
        self.assertEqual(map_axis(0,45,135,True,0.04),135)

    def test_deadzone_continuous_boundary(self):
        self.assertEqual(map_axis(0.519,45,135,False,0.04),90)
        self.assertAlmostEqual(map_axis(0.520001,45,135,False,0.04),90,places=3)

    def test_no_jump_on_first_hand_or_long_frame(self):
        motion = Motion()
        motion.observe((1,0),1)
        pan, tilt = motion.step(1)
        self.assertLessEqual(abs(pan-90),7)
        self.assertLessEqual(abs(tilt-90),7)

    def test_lost_hand_holds_current_not_old_target(self):
        motion = Motion()
        motion.observe((1,0),1/30)
        motion.step(1/30)
        old = (motion.pan,motion.tilt)
        motion.observe(None,1/30)
        for _ in range(100):
            motion.step(1/30)
        self.assertEqual((motion.pan,motion.tilt),old)

    def test_bad_observation_does_not_move(self):
        motion = Motion()
        motion.observe((float('nan'),0),1/30)
        self.assertEqual(motion.step(1/30),(90,90))

    def test_smoothing_independent_of_frame_rate(self):
        values = []
        for fps in (15,30,60):
            motion = Motion()
            motion.observe((0,0),1/fps)
            for _ in range(fps):
                motion.observe((1,1),1/fps)
            values.append(motion.filtered[0])
        self.assertAlmostEqual(values[0],values[1],places=10)
        self.assertAlmostEqual(values[1],values[2],places=10)

    def test_repeated_motion_stays_in_limits(self):
        motion = Motion()
        for point in ((0,0),(1,1),(0,1),(1,0)):
            for _ in range(100):
                motion.observe(point,1/30)
                pan,tilt = motion.step(1/30)
                self.assertTrue(45 <= pan <= 135)
                self.assertTrue(60 <= tilt <= 120)

    def test_invalid_settings_rejected(self):
        for settings in (Settings(pan_min=100),Settings(speed=0),Settings(smoothing=float('nan'))):
            with self.assertRaises(ValueError):
                settings.validate()

    def test_hand_in_image_center_keeps_calibrated_zero_pose(self):
        motion = Motion(home=(0, 0))
        for _ in range(60):
            motion.observe((0.5, 0.5), 1/30)
            self.assertEqual(motion.step(1/30), (0, 0))

    def test_zero_pose_uses_relative_spans_and_respects_servo_end(self):
        motion = Motion(home=(0, 0))
        motion.observe((1, 0), 1/30)
        self.assertEqual(motion.target, (45, 30))
        self.assertTrue(all(angle < 4 for angle in motion.step(1/30)))
        motion.hold()
        motion.observe((0, 1), 1/30)
        self.assertEqual(motion.target, (0, 0))
        motion.center()
        for _ in range(60):
            motion.step(1/30)
        self.assertEqual((motion.pan, motion.tilt), (0, 0))


if __name__ == '__main__':
    unittest.main()
