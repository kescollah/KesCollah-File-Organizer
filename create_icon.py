"""Script to generate professional multi-resolution .ico and .png icons for KesCollah.
"""

import os
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QImage, QPainter, QColor, QLinearGradient, QPolygonF
from PIL import Image

os.makedirs("assets", exist_ok=True)

def render_icon(size: int) -> QImage:
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)

    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Gradient background with rounded square
    grad = QLinearGradient(0.0, 0.0, float(size), float(size))
    grad.setColorAt(0.0, QColor("#00E5FF"))  # Electric Teal
    grad.setColorAt(0.6, QColor("#00B4D8"))  # Deep Cyan
    grad.setColorAt(1.0, QColor("#8B5CF6"))  # Electric Purple

    radius = float(size) * 0.22
    margin = float(size) * 0.05
    rect_size = float(size) - (margin * 2.0)

    painter.setBrush(grad)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(QRectF(margin, margin, rect_size, rect_size), radius, radius)

    # Dark inner container shape
    painter.setBrush(QColor("#0B0D14"))
    inner_margin = float(size) * 0.12
    inner_size = float(size) - (inner_margin * 2.0)
    painter.drawRoundedRect(QRectF(inner_margin, inner_margin, inner_size, inner_size), radius * 0.7, radius * 0.7)

    # Lightning bolt sorting symbol
    painter.setBrush(QColor("#00E5FF"))
    scale = float(size) / 64.0
    points = [
        QPointF(35.0 * scale, 14.0 * scale),
        QPointF(20.0 * scale, 34.0 * scale),
        QPointF(32.0 * scale, 34.0 * scale),
        QPointF(27.0 * scale, 50.0 * scale),
        QPointF(45.0 * scale, 28.0 * scale),
        QPointF(33.0 * scale, 28.0 * scale),
    ]
    painter.drawPolygon(QPolygonF(points))
    painter.end()
    return img

def main():
    # Render high-res PNG (256x256)
    img_256 = render_icon(256)
    img_256.save("assets/icon.png", "PNG")
    print("Saved assets/icon.png")

    # Render multiple sizes for Windows .ico
    sizes = [16, 32, 48, 64, 128, 256]
    pil_images = []
    for s in sizes:
        tmp_path = f"assets/tmp_{s}.png"
        render_icon(s).save(tmp_path, "PNG")
        pil_images.append(Image.open(tmp_path))

    pil_images[0].save(
        "assets/icon.ico",
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=pil_images[1:]
    )
    for s in sizes:
        try:
            os.remove(f"assets/tmp_{s}.png")
        except OSError:
            pass
    print("Saved assets/icon.ico with sizes [16, 32, 48, 64, 128, 256]!")

if __name__ == "__main__":
    main()
