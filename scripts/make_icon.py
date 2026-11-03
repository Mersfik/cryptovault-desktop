"""Gera logo.ico e logo.png a partir do SVG, sem dependências externas."""

from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QByteArray, QSize, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parents[1]
SVG = ROOT / "cryptovault" / "resources" / "logo.svg"
ICO = ROOT / "cryptovault" / "resources" / "logo.ico"
PNG = ROOT / "cryptovault" / "resources" / "logo.png"
SIZES = (16, 24, 32, 48, 64, 128, 256)


def render_png(renderer: QSvgRenderer, size: int) -> bytes:
    image = QImage(QSize(size, size), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    renderer.render(painter)
    painter.end()
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise RuntimeError("Falha ao codificar PNG do ícone.")
    return bytes(data)


def build_ico(images: list[tuple[int, bytes]]) -> bytes:
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries = bytearray()
    payload = bytearray()
    for size, data in images:
        dimension = 0 if size >= 256 else size
        entries += struct.pack(
            "<BBBBHHII",
            dimension,
            dimension,
            0,
            0,
            1,
            32,
            len(data),
            offset,
        )
        payload += data
        offset += len(data)
    return header + bytes(entries) + bytes(payload)


def main() -> int:
    app = QGuiApplication(sys.argv[:1])
    renderer = QSvgRenderer(str(SVG))
    if not renderer.isValid():
        print(f"SVG inválido: {SVG}", file=sys.stderr)
        return 1
    images = [(size, render_png(renderer, size)) for size in SIZES]
    ICO.write_bytes(build_ico(images))
    PNG.write_bytes(dict(images)[256])
    print(f"Gerado {ICO} ({ICO.stat().st_size} bytes)")
    print(f"Gerado {PNG} ({PNG.stat().st_size} bytes)")
    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
