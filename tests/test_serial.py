import unittest
from unittest.mock import patch
from hardware.serial_controller import SerialController
from tracking.motion import Motion


class Port:
    def __init__(self):
        self.rx = bytearray()
        self.writes = []
        self.closed = False

    @property
    def in_waiting(self):
        return len(self.rx)

    def read(self,count):
        data = bytes(self.rx[:count])
        del self.rx[:count]
        return data

    def write(self,data):
        self.writes.append(data)
        if data == b'HELLO\n':
            self.rx.extend(b'GLAZA 1\n')
        return len(data)

    def close(self):
        self.closed = True


class SerialTests(unittest.TestCase):
    def setUp(self):
        self.controller = SerialController()
        self.port = Port()
        self.controller.port = self.port

    def test_handshake_and_close(self):
        with patch('hardware.serial_controller.serial.Serial',return_value=self.port):
            self.controller.port = None
            self.controller.connect('TEST')
        self.assertIn(b'HELLO\n',self.port.writes)
        self.controller.close()
        self.assertTrue(self.port.closed)

    def test_board_rest_pose_survives_idle_then_follow_and_center(self):
        controller = SerialController()
        self.port.rx.extend(b'BOOT\nPOSE 180 0 180 0\n')
        with patch('hardware.serial_controller.serial.Serial', return_value=self.port):
            controller.connect('TEST')
        motion = Motion(home=controller.home, position=controller.position)
        controller.tick(*motion.step(1/30), now=1)
        self.assertEqual(self.port.writes[-1], b'S 1 180 0\n')
        motion.observe((0.5, 0.5), 1/30)
        self.assertEqual(motion.target, (180, 0))
        motion.observe((0, 0), 1/30)
        pan, tilt = motion.step(1/30)
        self.assertTrue(175 < pan < 180 and 0 < tilt < 5)
        motion.center()
        self.assertEqual(motion.step(1/30), (180, 0))
        with self.assertRaises(ValueError):
            controller.tick(0, 180, now=2)
        controller.close()
        self.assertEqual(controller.home, (90, 90))

    def test_cancelled_connection_closes_port(self):
        self.controller.port = None
        with patch('hardware.serial_controller.serial.Serial',return_value=self.port):
            with self.assertRaises(RuntimeError):
                self.controller.connect('TEST',lambda: True)
        self.assertTrue(self.port.closed)
        self.assertIsNone(self.controller.port)

    def test_servo_control_sketch_receives_only_decimal_pairs(self):
        controller = SerialController(csv_mode=True)
        with patch('hardware.serial_controller.serial.Serial', return_value=self.port) as open_port, patch(
            'hardware.serial_controller.time.monotonic', side_effect=[0.0, 2.1]
        ):
            controller.connect('TEST')
        open_port.assert_called_once_with('TEST', 9600, timeout=0, write_timeout=0.2)
        self.assertEqual(self.port.writes, [])
        controller.tick(90, 95, now=3.0)
        controller.tick(91, 95, now=3.01)
        controller.tick(92, 95, now=3.04)
        controller.tick(92, 95, now=5.0)
        self.assertEqual(self.port.writes, [b'90,95\n', b'92,95\n', b'92,95\n'])
        self.assertIsNone(controller.ack_angles)

    def test_servo_control_reports_short_write(self):
        controller = SerialController(csv_mode=True)
        controller.port = self.port
        with patch.object(self.port, 'write', return_value=1), self.assertRaises(RuntimeError):
            controller.tick(90, 90, now=1.0)
        self.assertIsNone(controller.last_angles)

    def test_partial_ack_does_not_queue_movements(self):
        c = self.controller
        c.tick(90,90,now=1)
        self.port.rx.extend(b'OK 1 90')
        c.tick(91,91,now=1.04)
        self.assertEqual(len(self.port.writes),1)
        self.port.rx.extend(b' 90\n')
        c.tick(92,92,now=1.08)
        self.assertEqual(c.ack_angles,(90,90))
        self.assertEqual(self.port.writes[-1],b'S 2 92 92\n')

    def test_wrong_ack_does_not_unblock(self):
        c = self.controller
        c.tick(90,90,now=1)
        self.port.rx.extend(b'OK 99 90 90\n')
        with self.assertRaises(RuntimeError):
            c.tick(100,100,now=1.8)
        self.assertEqual(len(self.port.writes),1)

    def test_board_restart_requires_reconnect(self):
        self.port.rx.extend(b'GLAZA 1\n')
        with self.assertRaises(RuntimeError):
            self.controller.tick(90,90,now=1)

    def test_out_of_range_commands_never_sent(self):
        with self.assertRaises(ValueError):
            self.controller.tick(0,180,now=1)
        self.assertEqual(self.port.writes,[])

    def test_rate_limit(self):
        c = self.controller
        c.tick(90,90,now=1)
        self.port.rx.extend(b'OK 1 90 90\n')
        c.tick(91,91,now=1.001)
        self.assertEqual(len(self.port.writes),1)
        c.tick(91,91,now=1.04)
        self.assertEqual(len(self.port.writes),2)


if __name__ == '__main__':
    unittest.main()
