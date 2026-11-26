import argparse
from pathlib import Path

import cv2


def main():
    parser = argparse.ArgumentParser(description="显示照片，按 s 保存，其他键退出。")
    parser.add_argument(
        "-i", "--input",
        required=True,
        type=Path,
        help="输入照片路径",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("saved_image.jpg"),
        help="保存路径，默认：saved_image.jpg",
    )
    args = parser.parse_args()

    if not args.input.is_file():
        parser.error(f"输入文件不存在：{args.input}")

    image = cv2.imread(str(args.input))

    if image is None:
        parser.error(f"无法读取照片，请检查文件格式或文件是否损坏：{args.input}")

    try:
        cv2.imshow("Display Image", image)
        print("请在图片窗口中按 s 保存，按其他键退出。")
        key = cv2.waitKey(0)

        if key == ord("s"):
            args.output.parent.mkdir(parents=True, exist_ok=True)

            if not cv2.imwrite(str(args.output), image):
                print(f"保存失败：{args.output}", file=sys.stderr)
                return 1

            print(f"图片已保存：{args.output.resolve()}")
        else:
            print("未保存图片。")
    finally:
        cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())