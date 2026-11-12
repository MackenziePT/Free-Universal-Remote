import unittest
from unittest.mock import patch, Mock
import desktop_unicode as du
from desktop_unicode import validate_click_coordinates, virtual_screen_bounds

class VirtualDesktopTests(unittest.TestCase):
    def test_secondary_monitor_can_have_negative_coordinates(self):
        rect=(-1920, -400, 3840, 1480)
        self.assertEqual(validate_click_coordinates(-1000, 50, rect), (-1000, 50))
        self.assertEqual(validate_click_coordinates(100, 100, rect), (100, 100))
        for bad in ((-1921,0), (3840,0), (0,-401), (0,1480)):
            with self.assertRaises(ValueError):
                validate_click_coordinates(*bad, rect)

    def test_click_coordinates_cannot_be_float_or_boolean(self):
        for x,y in ((True,5),(2.5,3),(0,False)):
            with self.assertRaises(ValueError):
                validate_click_coordinates(x,y,(0,0,1920,1080))

    def test_windows_metrics_expose_entire_virtual_screen(self):
        metrics = {76: -1600, 77: -300, 78: 3520, 79: 1380}
        dll = type('DLL', (), {})()
        dll.GetSystemMetrics = Mock(side_effect=lambda key: metrics[key])
        with patch.object(du.os, 'name', 'nt'), patch.object(du.ctypes, 'WinDLL', create=True, return_value=dll):
            self.assertEqual(du.virtual_screen_bounds(),(-1600,-300,1920,1080))

if __name__=='__main__': unittest.main()
