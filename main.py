# coding: utf-8
import os
import sys
import argparse
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

def load_image(path):
    """
    如果图片有透明区域，则先合成指定背景色（例如白色）。
    """
    try:
        with Image.open(path) as img:
            img = img.convert("RGBA")
            # 创建白色背景
            background = Image.new("RGBA", img.size, (255, 255, 255, 255))
            composite = Image.alpha_composite(background, img)
            # 转换为 RGB 模式（去掉 alpha 通道）
            composite = composite.convert("RGB")
            return ImageReader(composite)
    except Exception as e:
        return None
def preload_images(image_paths):
    """
    并行预加载图片，返回一个列表，每项为 (图片路径, ImageReader 对象) 的元组。
    如果加载失败，则 ImageReader 对象为 None。
    """
    results = []
    with ThreadPoolExecutor() as executor:
        # 使用 map 保持原有顺序
        readers = list(executor.map(load_image, image_paths))
        results = list(zip(image_paths, readers))
    return results

def create_pdf_from_folder(image_folder, output_filename):
    """
    从指定文件夹读取图片，并生成 PDF 文件。

    排版要求：
      - 版面始终分为 3×3 格（即使图片不足 9 张，也显示完整网格），
      - 每个卡牌（图片）尺寸为 59mm × 86mm，
      - 在卡牌周围预留 gap 区域绘制分割线（gap = 2mm），
      - 分割线不会与卡牌重叠，而是绘制在 gap 区域内，其长度正好为 gap 长。

    同时在终端显示生成进度。
    """
    # 支持的图片扩展名
    supported_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.gif')
    # 读取文件夹中所有图片文件（按文件名排序）
    image_paths = [os.path.join(image_folder, f) for f in os.listdir(image_folder)
                   if f.lower().endswith(supported_extensions)]
    image_paths.sort()

    total_cards = len(image_paths)

    # 预加载图片（并行）
    print("正在并行加载图片...")
    loaded_images = preload_images(image_paths)
    # 这里 loaded_images 为 [(path, ImageReader or None), ...] 列表

    # 设置参数
    card_width = 59 * mm      # 卡牌宽度
    card_height = 86 * mm     # 卡牌高度
    gap = 2 * mm              # 分割线预留间隙宽度（同时作为分割线的宽度或高度）
    columns = 3
    rows = 3

    # 整个网格尺寸（包括卡牌和 gap 区域）
    grid_width = columns * card_width + (columns + 1) * gap
    grid_height = rows * card_height + (rows + 1) * gap

    # 页面参数：A4
    page_width, page_height = A4
    # 居中网格在页面上
    left_margin = (page_width - grid_width) / 2
    bottom_margin = (page_height - grid_height) / 2

    # 创建 PDF 画布
    c = canvas.Canvas(output_filename, pagesize=A4)

    # 每页固定 9 格版面，不管实际图片数目如何
    cards_per_page = 9
    num_pages = (total_cards + cards_per_page - 1) // cards_per_page if total_cards > 0 else 1

    card_index = 0
    for page in range(num_pages):
        # 绘制卡牌（即使图片不足 9 张，其余区域留空）
        for row in range(rows):
            for col in range(columns):
                # 计算当前格子左下角坐标（卡牌绘制区域位于 gap 内部，不触及分割线）
                cell_x = left_margin + gap + col * (card_width + gap)
                # 为使第一行出现在页面上方，从上往下绘制
                cell_y = bottom_margin + gap + (rows - 1 - row) * (card_height + gap)

                if card_index < total_cards:
                    img_path, img_obj = loaded_images[card_index]
                    if img_obj is not None:
                        try:
                            # 绘制图片，保持长宽比居中显示
                            c.drawImage(img_obj, cell_x, cell_y,
                                        width=card_width, height=card_height,
                                        preserveAspectRatio=True, anchor='c')
                        except Exception as e:
                            # 如果图片加载出错，在区域内绘制提示
                            c.rect(cell_x, cell_y, card_width, card_height)
                            c.drawString(cell_x + 5, cell_y + card_height/2, "加载图片错误")
                    else:
                        # 图片加载失败，绘制提示
                        c.rect(cell_x, cell_y, card_width, card_height)
                        c.drawString(cell_x + 5, cell_y + card_height/2, "加载图片错误")
                    card_index += 1

                    # 显示进度
                    progress = f"生成进度: {card_index}/{total_cards} 张图片"
                    sys.stdout.write("\r" + progress)
                    sys.stdout.flush()
        # 若没有图片（即 total_cards==0），显示空白网格提示
        if total_cards == 0:
            sys.stdout.write("\r生成空白网格页...")

        # 绘制分割线——在 gap 区域形成完整的正方形网格交叉点
        for v in range(columns + 1):
            for h in range(rows + 1):
                x_square = left_margin + v * (card_width + gap)
                y_square = bottom_margin + h * (card_height + gap)
                c.setLineWidth(0.5)
                c.rect(x_square, y_square, gap, gap, stroke=1, fill=0)
        c.showPage()

    c.save()
    sys.stdout.write("\n")
    print(f"生成 PDF 文件：{output_filename}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="从文件夹读取图片生成 PDF 文件（固定 9 格版面，分割线不与卡牌重叠，并使用并行加载加速）"
    )
    parser.add_argument('image_folder', help="图片所在文件夹路径")
    parser.add_argument('--output', default="cards.pdf", help="输出 PDF 文件名")
    args = parser.parse_args()

    create_pdf_from_folder(args.image_folder, args.output)
