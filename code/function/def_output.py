"""显示和导出孔位结果；图片序号、终端和 CSV 使用同一份映射。"""
import csv
import json

import cv2
import numpy as np

STATUS_NAMES = {
    "decoded": "已解码",
    "unread": "未读出（空孔或漏读）",
    "ambiguous": "位置待复核",
    "conflict": "同孔多码冲突",
    "duplicate": "跨孔编号重复",
}


def _draw_code(image, result, label, color, scale):
    p = result.position
    points = np.int32([(q.x, q.y) for q in
                       (p.top_left, p.top_right, p.bottom_right, p.bottom_left)])
    cv2.polylines(image, [points], True, color, max(2, round(2 * scale)))
    x, y = points.min(axis=0)
    cv2.putText(image, label, (max(0, int(x)), max(round(24 * scale), int(y) - round(10 * scale))),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8 * scale, color, max(2, round(2 * scale)), cv2.LINE_AA)


def draw_plate(image, mapping):
    annotated = image.copy()
    scale = max(1.0, min(image.shape[:2]) / 1200)
    for well in mapping.wells:
        if well.results:
            color = (0, 180, 0) if well.status == "decoded" else (0, 0, 255)
            label = well.name if well.status == "decoded" else well.name + " !"
            for result in well.results:
                _draw_code(annotated, result, label, color, scale)
        else:
            x, y = (int(round(v)) for v in well.center)
            cv2.drawMarker(annotated, (x, y), (0, 165, 255), cv2.MARKER_CROSS, round(18 * scale), max(2, round(2 * scale)))
            cv2.putText(annotated, well.name + " ?", (max(0, x - round(25 * scale)), max(round(24 * scale), y - round(16 * scale))),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8 * scale, (0, 165, 255), max(2, round(2 * scale)), cv2.LINE_AA)
    for index, (result, _) in enumerate(mapping.unassigned, 1):
        _draw_code(annotated, result, f"OUT-{index}", (0, 0, 255), scale)
    return annotated


def print_plate(mapping):
    print("孔位\t状态\t样本编号 / 待复核候选")
    for well in mapping.wells:
        values = [result.text for result in well.results]
        display = repr(well.sample_id) if well.status == "decoded" else repr(values)
        print(f"{well.name}\t{STATUS_NAMES[well.status]}\t{display}")
    if mapping.unassigned:
        print(f"另有 {len(mapping.unassigned)} 个结果未分配到孔位：")
        for result, reason in mapping.unassigned:
            print(f"  {result.text!r}：{reason}")


def save_matrix(output_path, mapping):
    """按真实行列索引导出矩阵；默认 8 行×12 列，另带行列标题。"""
    rows = max(well.row for well in mapping.wells) + 1
    cols = max(well.column for well in mapping.wells) + 1
    matrix = [["" for _ in range(cols)] for _ in range(rows)]
    for well in mapping.wells:
        matrix[well.row][well.column] = well.sample_id
    matrix_path = output_path.with_name(output_path.stem + "_matrix.csv")
    matrix_path.parent.mkdir(parents=True, exist_ok=True)
    with matrix_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([""] + list(range(1, cols + 1)))
        for row, values in enumerate(matrix):
            writer.writerow([chr(65 + row)] + values)
    return matrix_path


def save_plate(output_path, annotated, mapping):
    """保存标注图、逐孔明细、矩阵和未分配结果；保留原有二项返回值。"""
    if output_path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}:
        raise ValueError("输出图片请使用 PNG、JPG、BMP 或 TIFF 扩展名。")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), annotated):
        raise OSError(f"无法保存标注图：{output_path}")
    csv_path = output_path.with_suffix(".csv")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["well", "row", "column", "sample_id", "status", "candidates", "mapping_mode"])
        for well in mapping.wells:
            writer.writerow([well.name, chr(65 + well.row), well.column + 1, well.sample_id,
                             well.status, json.dumps([r.text for r in well.results], ensure_ascii=False), mapping.mode])
    # 越界结果不能丢失，也不混入固定孔位表。
    unassigned_path = output_path.with_name(output_path.stem + "_unassigned.csv")
    with unassigned_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["content", "position", "reason"])
        for result, reason in mapping.unassigned:
            writer.writerow([result.text, str(result.position), reason])
    save_matrix(output_path, mapping)
    return csv_path, unassigned_path
