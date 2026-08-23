#!/usr/bin/env python3
"""
make_avatar.py — 缇雅 1:1 黄金比例头像生成器

将视频提取的 16:9 特写帧（public/tiya-frames/frame_*.webp）转换为
比例舒适、居中构图、带梦幻星空色彩延展的 1:1 高清头像（512x512）。

使用方式:
  python3 scripts/make_avatar.py 96 130 152 173 165
  python3 scripts/make_avatar.py --all
"""

import argparse
import sys
from pathlib import Path
from PIL import Image, ImageFilter, ImageDraw

ROOT_DIR = Path(__file__).resolve().parent.parent
FRAMES_DIR = ROOT_DIR / "public" / "tiya-frames"
BG_FILE = ROOT_DIR / "public" / "loading-1.webp"
OUT_DIR = ROOT_DIR / "public" / "avatars"


def generate_avatar(frame_num: int, output_path: Path, canvas_size: int = 512) -> bool:
    frame_name = f"frame_{frame_num:04d}.webp"
    frame_path = FRAMES_DIR / frame_name

    if not frame_path.exists():
        print(f"[-] 错误: 找不到帧文件 {frame_path}", file=sys.stderr)
        return False

    # 1. 创建 720x720 基础画布
    canvas = Image.new("RGBA", (720, 720), (28, 14, 48, 255))

    # 2. 提取 loading-1.webp 的梦幻星空紫色氛围作为背景延展
    if BG_FILE.exists():
        bg = Image.open(BG_FILE).convert("RGBA")
        bg_patch = bg.crop((1200, 300, 2000, 1100)).resize(
            (720, 720), Image.Resampling.LANCZOS
        )
        bg_patch = bg_patch.filter(ImageFilter.GaussianBlur(15))
        canvas.paste(bg_patch, (0, 0))

    # 3. 加载角色特写帧 (1280x720)，取中段包含头部与面部的核心区域
    fg = Image.open(frame_path).convert("RGBA")
    fg_crop = fg.crop((190, 0, 1090, 720)).resize(
        (700, 560), Image.Resampling.LANCZOS
    )

    # 4. 创建上下边缘平滑渐变羽化遮罩（保留面部 100% 锐利，消除上下硬边）
    f_mask = Image.new("L", (700, 560), 255)
    draw = ImageDraw.Draw(f_mask)
    feather_px = 40
    for y in range(feather_px):
        alpha = int(255 * (y / float(feather_px)))
        draw.line([(0, y), (700, y)], fill=alpha)
    for y in range(feather_px):
        alpha = int(255 * (y / float(feather_px)))
        draw.line([(0, 560 - 1 - y), (700, 560 - 1 - y)], fill=alpha)

    f_mask = f_mask.filter(ImageFilter.GaussianBlur(6))

    # 5. 居中贴合至画布 (720x720)
    canvas.paste(fg_crop, (10, 80), f_mask)

    # 6. 高清双线性缩放至目标尺寸 (如 512x512)
    avatar = canvas.resize((canvas_size, canvas_size), Image.Resampling.LANCZOS)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    avatar.save(output_path, "WEBP", quality=95)
    print(f"[+] 成功生成头像: {output_path.relative_to(ROOT_DIR)}")
    return True


def main():
    parser = argparse.ArgumentParser(description="缇雅 1:1 黄金比例头像生成器")
    parser.add_argument(
        "frames",
        nargs="*",
        type=int,
        help="待处理的帧编号 (例如: 96 130 152 173)",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=512,
        help="输出头像尺寸 (默认: 512)",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="输出目录 (默认: public/avatars/)",
    )

    args = parser.parse_args()
    out_dir = Path(args.out) if args.out else OUT_DIR

    if not args.frames:
        # 默认处理用户指定的核心 4 帧 + 笑颜帧
        frames = [96, 130, 152, 173, 165]
    else:
        frames = args.frames

    for num in frames:
        out_file = out_dir / f"tiya-avatar-{num:04d}.webp"
        generate_avatar(num, out_file, canvas_size=args.size)


if __name__ == "__main__":
    main()
