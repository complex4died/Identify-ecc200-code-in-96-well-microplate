import sys

import cv2

from function.def_decode import decode_ecc200
from function.def_grid import map_to_plate
from function.def_input import load_input, select_grid
from function.def_output import draw_plate, print_plate, save_plate


def main():
    image, output_path, args = load_input(include_options=True)
    try:
        results = decode_ecc200(image)
        print(f"成功解码的 ECC200 数量：{len(results)}")
        corners = args.corners
        if args.select_grid:
            corners = select_grid(image, args.rows, args.cols)
        elif corners is None:
            print("自动映射：假定图片左上为 A1、行列基本水平且各行列均有读码；请核对标注图。")

        mapping = map_to_plate(results, args.rows, args.cols, corners)
        print_plate(mapping)
        decoded = sum(w.status == "decoded" for w in mapping.wells)
        unread = sum(w.status == "unread" for w in mapping.wells)
        review = len(mapping.wells) - decoded - unread
        print(f"共 {len(mapping.wells)} 孔：已映射 {decoded}，未读出 {unread}，待复核 {review}，"
              f"未分配结果 {len(mapping.unassigned)}。")
        annotated = draw_plate(image, mapping)

        should_save = args.no_show
        if not args.no_show:
            scale = min(1.0, 1400 / image.shape[1], 900 / image.shape[0])
            cv2.imshow("ECC200 Plate Mapping", cv2.resize(annotated, None, fx=scale, fy=scale))
            print("绿色：已解码；橙色 ?：未读出；红色 !：需复核。按 s 保存原分辨率标注图和 CSV。")
            should_save = cv2.waitKey(0) & 0xFF == ord("s")
        if should_save:
            csv_path, unassigned_path = save_plate(output_path, annotated, mapping)
            print(f"标注图：{output_path.resolve()}")
            print(f"孔位明细表：{csv_path.resolve()}")
            matrix_path = output_path.with_name(output_path.stem + "_matrix.csv")
            print(f"孔位矩阵：{matrix_path.resolve()}")
            print(f"未分配结果表：{unassigned_path.resolve()}")
        else:
            print("未保存结果。")
    except (cv2.error, OSError, ValueError, RuntimeError) as error:
        print(f"处理失败：{error}", file=sys.stderr)
        return 1
    finally:
        if not args.no_show:
            cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())
