import math
import unittest
from native_lab.schema import validate
from native_lab.geometry import ordered_paths, intersections, gap_at


class ContractTests(unittest.TestCase):
    def test_invalid_numbers_and_unknown_fields(self):
        for value in [True, math.nan, math.inf, "10", -1]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate({"model": "etch", "params": {"grid_nm": value}})
        with self.assertRaises(ValueError):
            validate({"model": "etch", "params": {"made_up": 1}})

    def test_geometry_resolution_and_integer_contract(self):
        for params in [{"width_nm": 350}, {"grid_nm": 20}, {"seed": 1.2}]:
            with self.subTest(params=params), self.assertRaises(ValueError):
                validate({"model": "etch", "params": params})

    def test_export_retains_open_boundary_and_closed_void(self):
        nodes = [[-1, 0], [0, -1], [1, 0], [-.1, -.2], [.1, -.2], [0, -.4]]
        lines = [[1, 2], [3, 4], [0, 1], [5, 3], [4, 5]]
        paths = ordered_paths(nodes, lines)
        self.assertEqual(len(paths), 2)
        self.assertEqual(sum(len(p)-1 for p in paths), len(lines))
        self.assertEqual(sum(p[0] == p[-1] for p in paths), 1)

    def test_profile_measurement_uses_line_intersections(self):
        paths = [[[-100, 0], [-30, 0], [-30, -200], [30, -200], [30, 0], [100, 0]]]
        self.assertEqual(intersections(paths, 0, 0), [-200])
        self.assertEqual(gap_at(paths, -100), 60)


if __name__ == "__main__":
    unittest.main()
