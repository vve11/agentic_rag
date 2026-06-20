from __future__ import annotations

from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont


ROOT = Path("/Users/at/Desktop/paper-rag-agent")
OUT = ROOT / "marketing/xhs/assets"
UI_SOURCE = ROOT / "data/index/eval_runs/paper_rag_deerflow_style.png"
W, H = 1080, 1350


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size, index=1 if bold else 0)
    return ImageFont.load_default()


FONT_TITLE = font(64, True)
FONT_SUB = font(34)
FONT_BODY = font(32)
FONT_SMALL = font(25)
FONT_TAG = font(24, True)


def make_canvas() -> Image.Image:
    img = Image.new("RGB", (W, H), "#f8f5ef")
    draw = ImageDraw.Draw(img)
    for i in range(0, H, 9):
        shade = 248 - min(18, i // 80)
        draw.line((0, i, W, i), fill=(shade, shade - 2, shade - 7))
    return img


def rounded(draw: ImageDraw.ImageDraw, box, radius=28, fill="#ffffff", outline="#ded8cc", width=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def text(draw, xy, value, fnt, fill="#111827", spacing=8):
    draw.multiline_text(xy, value, font=fnt, fill=fill, spacing=spacing)


def draw_header(draw, eyebrow: str):
    draw.rounded_rectangle((64, 54, 64 + len(eyebrow) * 25 + 42, 104), 25, fill="#111827")
    draw.text((86, 65), eyebrow, font=FONT_TAG, fill="#ffffff")


def bullet_lines(draw, x: int, y: int, items: list[str], color="#1f2937") -> int:
    for item in items:
        draw.ellipse((x, y + 12, x + 12, y + 24), fill="#111827")
        text(draw, (x + 30, y), item, FONT_BODY, fill=color)
        y += 58
    return y


def save(img: Image.Image, name: str):
    OUT.mkdir(parents=True, exist_ok=True)
    img.save(OUT / name, quality=95)


def card_cover():
    img = make_canvas()
    draw = ImageDraw.Draw(img)
    draw_header(draw, "AI项目课")
    text(draw, (70, 185), "我做了一个\n能写进简历的\nAgent 项目", FONT_TITLE, spacing=16)
    text(draw, (74, 550), "Paper RAG Agent", font(46, True), "#111827")
    text(draw, (74, 615), "一个面向论文研读的 AI 工作台", FONT_SUB, "#374151")
    rounded(draw, (70, 735, 1010, 1015), 36, "#ffffff", "#e5ded1")
    bullet_lines(
        draw,
        110,
        785,
        [
            "不是普通聊天机器人",
            "不是智能客服模板",
            "是可以演示、答辩、写简历的完整项目",
        ],
    )
    text(draw, (74, 1185), "适合：想做 AI Agent / RAG 项目的同学", FONT_SMALL, "#6b7280")
    save(img, "01_cover.png")


def card_ui():
    img = make_canvas()
    draw = ImageDraw.Draw(img)
    draw_header(draw, "前端UI")
    text(draw, (70, 145), "项目不是停在命令行\n而是做成了工作台", font(52, True), spacing=10)
    if UI_SOURCE.exists():
        ui = Image.open(UI_SOURCE).convert("RGB")
        ui.thumbnail((940, 660))
        x = (W - ui.width) // 2
        rounded(draw, (x - 16, 430 - 16, x + ui.width + 16, 430 + ui.height + 16), 30, "#ffffff", "#ded8cc")
        img.paste(ui, (x, 430))
    text(draw, (70, 1130), "从论文问题、资料管理到演示状态，都能在同一个页面里完成。", FONT_BODY, "#374151")
    save(img, "02_ui_workspace.png")


def card_value():
    img = make_canvas()
    draw = ImageDraw.Draw(img)
    draw_header(draw, "项目能做什么")
    text(draw, (70, 150), "它更像一个\n论文研读助手", font(58, True), spacing=12)
    rounded(draw, (70, 360, 1010, 1020), 34, "#ffffff", "#ded8cc")
    bullet_lines(
        draw,
        120,
        430,
        [
            "导入论文并整理成可检索资料",
            "围绕论文内容进行问答",
            "回答时展示引用证据",
            "生成论文 Wiki / 知识笔记",
            "记录反馈，方便继续优化",
            "可以作为课堂演示和面试项目",
        ],
    )
    text(draw, (72, 1175), "公开帖只讲效果，不展开具体实现细节。", FONT_SMALL, "#6b7280")
    save(img, "03_project_value.png")


def card_difference():
    img = make_canvas()
    draw = ImageDraw.Draw(img)
    draw_header(draw, "区别")
    text(draw, (70, 140), "它和“智能客服 Agent”\n不是一类项目", font(52, True), spacing=10)
    rounded(draw, (64, 360, 516, 1030), 28, "#ffffff", "#ded8cc")
    rounded(draw, (564, 360, 1016, 1030), 28, "#111827", "#111827")
    text(draw, (105, 410), "智能客服", font(40, True), "#111827")
    text(draw, (605, 410), "Paper RAG Agent", font(38, True), "#ffffff")
    text(draw, (105, 510), "更偏业务接待\nFAQ 回复\n售前售后流程\n固定话术", FONT_BODY, "#374151", spacing=18)
    text(draw, (605, 510), "更偏知识研读\n论文问答\n证据引用\n项目答辩", FONT_BODY, "#f9fafb", spacing=18)
    text(draw, (105, 850), "关键词：服务流程", FONT_SMALL, "#6b7280")
    text(draw, (605, 850), "关键词：学习成果", FONT_SMALL, "#d1d5db")
    text(draw, (72, 1160), "一个适合讲“我做过完整 AI 应用”的项目。", FONT_BODY, "#374151")
    save(img, "04_difference.png")


def card_audience():
    img = make_canvas()
    draw = ImageDraw.Draw(img)
    draw_header(draw, "适合谁")
    text(draw, (70, 145), "如果你想做一个\n能被追问的 AI 项目", font(54, True), spacing=10)
    rounded(draw, (70, 360, 1010, 1050), 34, "#ffffff", "#ded8cc")
    bullet_lines(
        draw,
        120,
        430,
        [
            "想把 Agent / RAG 写进简历",
            "不想只做一个 API 调用 demo",
            "希望项目有前端、有后端、有演示",
            "希望面试时能讲清项目边界",
            "想用一个项目串起 AI 应用开发能力",
        ],
    )
    text(draw, (72, 1180), "目标：不是堆名词，而是做出可以展示的作品。", FONT_SMALL, "#6b7280")
    save(img, "05_audience.png")


def card_course():
    img = make_canvas()
    draw = ImageDraw.Draw(img)
    draw_header(draw, "课程交付")
    text(draw, (70, 145), "完整版本会提供\n项目 + 手册 + 演示路径", font(52, True), spacing=10)
    rounded(draw, (70, 380, 1010, 1025), 34, "#ffffff", "#ded8cc")
    bullet_lines(
        draw,
        120,
        445,
        [
            "完整项目源码与运行说明",
            "课程手册和学习路径",
            "标准演示问题与答辩材料",
            "简历包装和面试表达建议",
            "常见报错排查清单",
        ],
    )
    text(draw, (74, 1148), "公开内容只展示项目方向，完整细节随课程交付。", FONT_BODY, "#374151")
    save(img, "06_course_pack.png")


def main():
    card_cover()
    card_ui()
    card_value()
    card_difference()
    card_audience()
    card_course()
    print(OUT)


if __name__ == "__main__":
    main()
