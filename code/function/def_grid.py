"""根据标签中心拟合孔板网格，保留未读出孔位；不根据样本编号推测位置。"""
from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass
class Well:
    name: str
    row: int
    column: int
    center: tuple
    results: list = field(default_factory=list)
    status: str = "unread"

    @property
    def sample_id(self):
        # 只有单一且位置可靠的结果进入正式编号列。
        return self.results[0].text if self.status == "decoded" else ""


@dataclass
class PlateMapping:
    wells: list
    unassigned: list
    image_to_grid: np.ndarray
    mode: str


def barcode_center(result):
    p = result.position
    corners = [p.top_left, p.top_right, p.bottom_right, p.bottom_left]
    return np.mean([(q.x, q.y) for q in corners], axis=0)


def _project(points, matrix):
    points = np.asarray(points, dtype=np.float64).reshape(-1, 1, 2)
    return cv2.perspectiveTransform(points, matrix).reshape(-1, 2)


def _axis_groups(values, count):
    """仅用于近似横平竖直、所有行列都有读取结果时的初始分组。"""
    centers = np.linspace(values.min(), values.max(), count)
    for _ in range(50):
        labels = np.argmin(abs(values[:, None] - centers), axis=1)
        if any(np.count_nonzero(labels == i) < 2 for i in range(count)):
            raise ValueError("某行或某列读取结果不足，无法可靠自动定位；请使用 --select-grid。")
        updated = np.array([np.median(values[labels == i]) for i in range(count)])
        if np.allclose(updated, centers):
            break
        centers = updated
    gaps = np.diff(centers)
    if gaps.min() <= 0 or gaps.max() / gaps.min() > 1.6:
        raise ValueError("行列间距不一致，可能存在整行漏读或倾斜；请使用 --select-grid。")
    return labels


def _manual_transform(corners, rows, cols):
    # 顺序为四个角孔的中心：A1、A末列、末行末列、末行1；不是板架外轮廓。
    source = np.asarray(corners, dtype=np.float32).reshape(4, 2)
    if not np.isfinite(source).all() or not cv2.isContourConvex(source):
        raise ValueError("四个角孔中心必须形成不交叉的凸四边形，请检查点击顺序。")
    if abs(cv2.contourArea(source)) < 16:
        raise ValueError("四角区域过小，请重新选择四个角孔中心。")
    target = np.float32([[0, 0], [cols - 1, 0], [cols - 1, rows - 1], [0, rows - 1]])
    matrix = cv2.getPerspectiveTransform(source, target)
    if not np.isfinite(matrix).all() or abs(np.linalg.det(matrix)) < 1e-12:
        raise ValueError("无法建立四角映射，请重新选择角孔中心。")
    return matrix


def _auto_transform(points, rows, cols):
    if len(points) < max(4, rows * 2, cols * 2):
        raise ValueError("读取结果不足以拟合完整孔板；请使用 --select-grid 指定四角孔中心。")
    columns = _axis_groups(points[:, 0], cols)
    row_ids = _axis_groups(points[:, 1], rows)
    grid = np.column_stack([columns, row_ids]).astype(np.float64)
    matrix, inliers = cv2.findHomography(points, grid, cv2.RANSAC, 0.30)
    if matrix is None or inliers is None or inliers.mean() < 0.85:
        raise ValueError("自动网格拟合不可靠，请使用 --select-grid 校准。")
    # 不能把 RANSAC 丢弃的所有边缘行/列继续当作可靠的板边。
    mask = inliers.ravel().astype(bool)
    if len(set(row_ids[mask])) != rows or len(set(columns[mask])) != cols:
        raise ValueError("自动网格缺少边界支持，请使用 --select-grid 校准。")
    projected = _project(points, matrix)
    if not np.isfinite(projected).all():
        raise ValueError("自动网格无效，请手动指定四角。")
    return matrix


def map_to_plate(results, rows=8, cols=12, corners=None):
    """返回按行排序的全部孔位；自动模式假定左上为 A1 且所有行列均有读码。"""
    if not 2 <= rows <= 26 or not 2 <= cols <= 48:
        raise ValueError("行数应为 2～26，列数应为 2～48。")
    results = list(results)
    points = np.array([barcode_center(r) for r in results], dtype=float).reshape(-1, 2)
    mode = "manual" if corners is not None else "auto"
    matrix = (_manual_transform(corners, rows, cols) if corners is not None
              else _auto_transform(points, rows, cols))
    grid_points = [(col, row) for row in range(rows) for col in range(cols)]
    image_centers = _project(grid_points, np.linalg.inv(matrix))
    wells = [Well(f"{chr(65 + row)}{col + 1}", row, col, tuple(center))
             for (col, row), center in zip(grid_points, image_centers)]
    unassigned = []
    mapped = _project(points, matrix) if len(points) else []
    for result, (x, y) in zip(results, mapped):
        if not np.isfinite([x, y]).all():
            unassigned.append((result, "invalid_position"))
            continue
        col, row = int(np.floor(x + 0.5)), int(np.floor(y + 0.5))
        if not (0 <= col < cols and 0 <= row < rows):
            unassigned.append((result, "outside_grid"))
            continue
        well = wells[row * cols + col]
        well.results.append(result)
        if max(abs(x - col), abs(y - row)) > 0.35:
            well.status = "ambiguous"
        elif well.status != "ambiguous":
            well.status = "decoded"
    for well in wells:
        if len(well.results) > 1:
            well.status = "conflict"
    by_value = {}
    for well in wells:
        if well.status == "decoded":
            by_value.setdefault(well.sample_id, []).append(well)
    for group in by_value.values():
        if len(group) > 1:
            for well in group:
                well.status = "duplicate"
    return PlateMapping(wells, unassigned, matrix, mode)
