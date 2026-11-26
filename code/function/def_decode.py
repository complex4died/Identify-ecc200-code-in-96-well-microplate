"""整图解码 Data Matrix ECC200，并标出成功解码的位置。"""

import cv2
import numpy as np
import zxingcpp


def decode_ecc200(image):
    """返回成功解码的结果；每个结果包含 text 和 position。"""
    return zxingcpp.read_barcodes(
        image,
        formats=zxingcpp.BarcodeFormat.DataMatrix,
        try_rotate=True,
        try_downscale=True,
        try_invert=True,
        return_errors=False,
    )


def draw_results(image, results):
    """在图片副本上画四角边框和序号，不修改原始图片。"""
    annotated = image.copy()

    for index, result in enumerate(results, start=1):
        position = result.position
        corners = [
            position.top_left,
            position.top_right,
            position.bottom_right,
            position.bottom_left,
        ]
        points = np.array([(point.x, point.y) for point in corners], dtype=np.int32)
        cv2.polylines(annotated, [points], True, (0, 255, 0), 2)

        # 图上只显示序号，完整内容在终端打印，避免中文字体显示问题。
        x = max(0, int(points[:, 0].min()))
        y = max(20, int(points[:, 1].min()) - 8)
        cv2.putText(
            annotated, f"#{index}", (x, y),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2,
        )

    return annotated
