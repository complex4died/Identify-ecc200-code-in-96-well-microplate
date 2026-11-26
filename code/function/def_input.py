import argparse
from pathlib import Path

import cv2


def resolve_output_path(input_path, output_path):
    """现有目录或无扩展名路径作为目录，生成输入文件名_mapped.png。"""
    output_path = Path(output_path).expanduser()
    if output_path.is_dir() or not output_path.suffix:
        if output_path.exists() and not output_path.is_dir():
            raise ValueError(f"输出目录被同名文件占用：{output_path}")
        output_path = output_path / f"{Path(input_path).stem}_mapped.png"
    if output_path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}:
        raise ValueError("-o 请指定输出目录或 PNG、JPG、BMP、TIFF 图片路径。")
    if Path(input_path).resolve() == output_path.resolve():
        raise ValueError("输出路径不能与原始照片相同。")
    for parent in output_path.parents:
        if parent.exists() and not parent.is_dir():
            raise ValueError(f"输出目录被同名文件占用：{parent}")
    return output_path


def load_input(include_options=False):
    """读取照片；默认保留原来的二项返回值，主程序可额外获取参数。"""
    parser = argparse.ArgumentParser(description="ECC200 解码、空间排序和孔位映射。")
    parser.add_argument("-i", "--input", required=True, type=Path, help="输入照片路径")
    parser.add_argument("-o", "--output", type=Path, default=Path("saved_image.png"),
                        help="输出目录或图片路径；目录默认生成 输入文件名_mapped.png；不指定则为 saved_image.png")
    parser.add_argument("--rows", type=int, default=8, help="孔板行数，默认 8")
    parser.add_argument("--cols", type=int, default=12, help="孔板列数，默认 12")
    calibration = parser.add_mutually_exclusive_group()
    calibration.add_argument("--select-grid", action="store_true", help="鼠标依次点击四个角孔中心")
    calibration.add_argument("--corners", type=float, nargs=8, metavar="N",
                             help="四角孔中心原图坐标：A1、A末列、末行末列、末行1，共 8 个数")
    parser.add_argument("--no-show", action="store_true", help="不打开窗口，直接保存标注图和 CSV")
    args = parser.parse_args()
    if not 2 <= args.rows <= 26 or not 2 <= args.cols <= 48:
        parser.error("行数应为 2～26，列数应为 2～48。")
    if args.select_grid and args.no_show:
        parser.error("--select-grid 需要窗口，不能与 --no-show 同用；可改用 --corners。")
    if not args.input.is_file():
        parser.error(f"输入文件不存在：{args.input}")
    try:
        args.output = resolve_output_path(args.input, args.output)
    except ValueError as error:
        parser.error(str(error))
    image = cv2.imread(str(args.input))
    if image is None:
        parser.error(f"无法读取照片，请检查格式或文件是否损坏：{args.input}")
    if include_options:
        return image, args.output, args
    return image, args.output


def select_grid(image, rows, cols):
    """按显示缩放比例将鼠标点击还原到原图坐标。"""
    last_row = chr(64 + rows)
    names = ["A1", f"A{cols}", f"{last_row}{cols}", f"{last_row}1"]
    scale = min(1.0, 1200 / image.shape[1], 800 / image.shape[0])
    preview = cv2.resize(image, None, fx=scale, fy=scale)
    # resize 会取整，用实际宽高比例回算点击坐标。
    sx, sy = preview.shape[1] / image.shape[1], preview.shape[0] / image.shape[0]
    clicks = []
    title = "Select corner WELL CENTERS"

    def on_click(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and len(clicks) < 4:
            clicks.append((x / sx, y / sy))
        elif event == cv2.EVENT_RBUTTONDOWN and clicks:
            clicks.pop()

    print("依次点击角孔中心：" + " → ".join(names))
    print("点击孔中心，不是板架外边角；空孔也按理论中心点击。右键撤销，Enter 确认，Esc 取消。")
    cv2.namedWindow(title)
    cv2.setMouseCallback(title, on_click)
    try:
        while True:
            frame = preview.copy()
            for name, (x, y) in zip(names, clicks):
                point = (round(x * sx), round(y * sy))
                cv2.circle(frame, point, 6, (0, 0, 255), -1)
                cv2.putText(frame, name, (point[0] + 8, point[1]), cv2.FONT_HERSHEY_SIMPLEX,
                            0.6, (0, 0, 255), 2)
            cv2.imshow(title, frame)
            key = cv2.waitKey(30) & 0xFF
            if key in (10, 13) and len(clicks) == 4:
                return clicks
            if key == 27 or cv2.getWindowProperty(title, cv2.WND_PROP_VISIBLE) < 1:
                raise ValueError("已取消孔板校准。")
    finally:
        cv2.destroyWindow(title)
