# ECC200 图片识别与孔位映射

## 安装依赖

已在 macOS、Python 3.12 环境完成测试。新环境可按下列方式安装：

```bash
conda create -n ecc200 python=3.12
conda activate ecc200
python -m pip install -r requirements.txt
```

`requirements.txt` 固定了本次通过测试的 NumPy、OpenCV 和 ZXing-C++ 版本。
Windows 尚未进行实机验证；高拍仪采集尚未接入，当前输入为本地图片。

在 `ecc200` 环境中，从项目目录运行：

```bash
conda activate ecc200
python code/main.py -i datas/simulation_real_1.jpg -o dir_work/plate_mapped.png
```

默认 8 行、12 列，以图片左上为 A1，从左到右、从上到下输出 A1～H12。
图片窗口按 `s` 保存原分辨率标注图、同名孔位明细 CSV、`_matrix.csv` 孔位矩阵和 `_unassigned.csv` 未分配结果表。
窗口只缩放预览，解码和保存都使用原图分辨率。

直接保存、不打开窗口：

```bash
python code/main.py -i datas/simulation_real_1.jpg -o dir_work/plate_mapped.png --no-show
```

## 输出目录和格式

`-o` 可以直接指定目录（现有目录或无扩展名路径）。不存在的目录在保存时创建：

```bash
python code/main.py -i datas/simulation_real_1.jpg -o dir_work --no-show
```

该命令生成 `dir_work/simulation_real_1_mapped.png`、同名 `.csv`、`_matrix.csv` 和 `_unassigned.csv`。
无扩展名路径统一视为目录，例如 `-o results` 会创建 `results/`。
若想指定文件名，写完整扩展名，例如 `-o dir_work/result.png` 或 `-o dir_work/result.jpg`。
省略 `-o` 时默认输出当前目录下的 `saved_image.png` 和配套 CSV。
不支持的扩展名在启动时提示，不再等按下保存键才报错。

## 模块职责

- `code/main.py`：连接输入、解码、孔位映射、显示和保存流程。
- `code/function/def_input.py`：参数解析、图片读取、手动选取角孔中心。
- `code/function/def_decode.py`：ZXing-C++ 整图解码 Data Matrix ECC200。
- `code/function/def_grid.py`：计算码中心、拟合透视网格、保留完整孔位和异常状态。
- `code/function/def_output.py`：终端输出、孔位标注、CSV 导出。

## 自动映射的条件

自动模式先对中心坐标分行、分列，再拟合二维透视变换。它适用于完整入镜、
行列大致水平、每行每列至少有两个成功解码结果的规则孔板。
它不根据样本编号推断孔位，也不恢复漏读编号。

自动模式依赖上述假设，并非可靠识别板架外轮廓或 A1 标记；
裁掉整行、强烈旋转、严重透视、整行整列漏读时不能保证自动定位。
程序会拒绝部分不可靠的拟合，但不能发现所有几何歧义；请核对叠加图。
没有方向标记时无法自动判断孔板是否旋转了 180°。

## 手动指定四角孔中心

自动拟合失败、方向不同或行列倾斜明显时：

```bash
python code/main.py -i datas/simulation_real_1.jpg -o dir_work/manual.png --select-grid
```

依次点击 **A1、A12、H12、H1 的孔中心**，不是板架外边角，也不是二维码边角。
角孔没有标签时点击该孔的理论中心。右键撤销，Enter 确认，Esc 取消。
手动模式可以明确指定真实 A1 方向。保持四个角孔中心大致共面。

也可以提供原图像素坐标，不使用窗口（下面数值仅示例，不对应你的照片）：

```bash
python code/main.py -i your_photo.jpg -o dir_work/manual.png --corners 100 100 1200 100 1200 800 100 800 --no-show
```

小示例图使用 2×2 网格：

```bash
python code/main.py -i datas/ecc200_demo.png -o dir_work/demo.png --rows 2 --cols 2
```

`simulation_1.png` 是普通 QR Code 模拟图，不是 ECC200；本程序只解码 Data Matrix。

## 孔位矩阵 CSV

保存时自动额外生成 `输出文件名_matrix.csv`，无需新增参数。
默认数据区为 **12 列、8 行**，列名 1～12、行名 A～H；包含标题后文件为 9 行、13 列。
单元格内容为对应孔位的样本编号。未读出、位置歧义、冲突或重复编号均留空，详情查阅逐孔明细表。
不会把后面的编号前移。矩阵尺寸跟随 `--rows` 和 `--cols`，也支持 2×2 示例图。

## 状态和输出

CSV 始终保留全部孔位，默认共 96 行，不会因漏读而把后面的编号前移。
只有 `decoded` 状态写入正式 `sample_id`；其他状态保持该列空白，已读取内容放在 `candidates` 列供核对。

| 状态 | 含义 | 图上显示 |
|---|---|---|
| decoded | 单一且位置符合网格的解码结果 | 绿色框、孔位名 |
| unread | 没有成功解码结果，无法区分空孔和漏读 | 橙色十字、孔位名 ? |
| ambiguous | 标签中心偏离理论孔位超过间距的 35% | 红色框、孔位名 ! |
| conflict | 同一孔位有多个候选码 | 红色框、孔位名 ! |
| duplicate | 不同孔位读出相同编号，需复核 | 红色框、孔位名 ! |

网格外的读取结果单独保存到 `_unassigned.csv`，不混入孔位表。
重复运行相同 `-o` 会替换对应输出文件；输出图片不能与输入照片同路径。

## 检查

```bash
python -B -m unittest discover -s tests -v
```

测试包含结果乱序、局部漏读、整行/整列漏读、轻微透视、手动透视定位、
同孔冲突、边界歧义、重复编号、越界结果和完整 CSV 导出。
合成测试证明映射逻辑，不代表真实样本编号已获人工确认。
