"""孔位映射回归检查：用已知坐标验证，不通过样本编号推断位置。"""
import csv
import random
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from function.def_grid import map_to_plate
from function.def_output import draw_plate, save_plate


def barcode(x, y, text):
    def point(dx, dy):
        return SimpleNamespace(x=x + dx, y=y + dy)
    return SimpleNamespace(text=text, position=SimpleNamespace(
        top_left=point(-8, -8), top_right=point(8, -8),
        bottom_right=point(8, 8), bottom_left=point(-8, 8)))


def plate(missing=(), perspective=False):
    transform = np.array([[95., 3., 100.], [2., 100., 100.],
                          [.001, .002, 1.]]) if perspective else np.array(
                              [[100., 0., 100.], [0., 100., 100.], [0., 0., 1.]])
    records = []
    for row in range(8):
        for col in range(12):
            name = f"{chr(65+row)}{col+1}"
            if name in missing:
                continue
            # 偏移模拟同一排管盖的高低变化。
            offset = 0.08 if (row + col) % 2 else -0.08
            p = transform @ [col, row + offset, 1]
            records.append(barcode(p[0] / p[2], p[1] / p[2], name))
    random.Random(42).shuffle(records)
    return records


class GridTests(unittest.TestCase):
    def test_shuffled_perspective_and_missing_slots(self):
        missing = {'A2', 'C4', 'E7'} | {f'H{col}' for col in range(7, 13)}
        mapping = map_to_plate(plate(missing, perspective=True))
        self.assertEqual(len(mapping.wells), 96)
        self.assertEqual([w.name for w in mapping.wells[:13]],
                         [f'A{i}' for i in range(1, 13)] + ['B1'])
        for well in mapping.wells:
            self.assertEqual(well.sample_id, '' if well.name in missing else well.name)
        self.assertFalse(mapping.unassigned)

    def test_entire_missing_row_requires_calibration(self):
        with self.assertRaises(ValueError):
            map_to_plate(plate({f'D{i}' for i in range(1, 13)}))

    def test_entire_missing_column_requires_calibration(self):
        with self.assertRaises(ValueError):
            map_to_plate(plate({f'{chr(65+r)}5' for r in range(8)}))

    def test_missing_edge_row_rejected(self):
        with self.assertRaises(ValueError):
            map_to_plate(plate({f'A{i}' for i in range(1, 13)}))

    def test_manual_perspective_with_sparse_results(self):
        corners = np.float32([[600, 70], [900, 600], [400, 900], [80, 300]])
        grid = np.float32([[0, 0], [11, 0], [11, 7], [0, 7]])
        transform = cv2.getPerspectiveTransform(grid, corners)
        p = transform @ [4, 2, 1]
        result = barcode(p[0]/p[2], p[1]/p[2], 'known')
        mapping = map_to_plate([result], corners=corners)
        self.assertEqual(mapping.wells[2*12+4].sample_id, 'known')
        self.assertEqual(sum(w.status == 'unread' for w in mapping.wells), 95)

    def test_conflict_ambiguity_duplicates_and_outside(self):
        corners = [[100,100], [1200,100], [1200,800], [100,800]]
        records = [barcode(100,100,'x'), barcode(105,100,'y'),
                   barcode(200,100,'same'), barcode(300,100,'same'),
                   barcode(445,100,'boundary'), barcode(2000,100,'outside')]
        mapping = map_to_plate(records, corners=corners)
        self.assertEqual([w.status for w in mapping.wells[:4]],
                         ['conflict', 'duplicate', 'duplicate', 'ambiguous'])
        self.assertTrue(all(w.sample_id == '' for w in mapping.wells[:4]))
        self.assertEqual(mapping.unassigned[0][0].text, 'outside')

    def test_blank_requires_manual_calibration(self):
        with self.assertRaises(ValueError):
            map_to_plate([])
        mapping = map_to_plate([], corners=[[100,100],[1200,100],[1200,800],[100,800]])
        self.assertTrue(all(w.status == 'unread' for w in mapping.wells))

    def test_invalid_corners_and_dimensions(self):
        for corners in ([[0,0]]*4, [[0,0],[100,100],[100,0],[0,100]]):
            with self.assertRaises(ValueError):
                map_to_plate([], corners=corners)
        with self.assertRaises(ValueError):
            map_to_plate([], rows=1)

    def test_export_preserves_96_rows_and_does_not_modify_source(self):
        mapping = map_to_plate(plate({'A2'}))
        source = np.full((950, 1350, 3), 255, np.uint8)
        before = source.copy()
        annotated = draw_plate(source, mapping)
        self.assertTrue(np.array_equal(source, before))
        self.assertFalse(np.array_equal(source, annotated))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'mapped.png'
            csv_path, unassigned_path = save_plate(path, annotated, mapping)
            with csv_path.open(encoding='utf-8-sig', newline='') as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 96)
            self.assertEqual(rows[1]['well'], 'A2')
            self.assertEqual(rows[1]['sample_id'], '')
            self.assertEqual(rows[2]['sample_id'], 'A3')
            self.assertEqual(rows[-1]['well'], 'H12')
            self.assertTrue(unassigned_path.is_file())
            self.assertTrue(np.array_equal(cv2.imread(str(path)), annotated))


if __name__ == '__main__':
    unittest.main()
