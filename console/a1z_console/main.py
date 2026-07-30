"""Application entry point for the A1Z Qt/QML console."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QTimer, QUrl
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, QQmlEngine
from PySide6.QtQuickControls2 import QQuickStyle

from .controller import ConsoleController


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=["sim", "real"], default="sim")
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Load the complete QML scene offscreen and exit after 1.5 seconds.",
    )
    parser.add_argument(
        "--screenshot",
        type=Path,
        help="Save one rendered window image and exit (for visual validation).",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    package_dir = Path(__file__).resolve().parent
    repo_root = package_dir.parents[1]
    qml_root = package_dir.parent / "qml"

    QCoreApplication.setOrganizationName("A1Z")
    QCoreApplication.setApplicationName("A1Z Console")
    QQuickStyle.setStyle("Basic")
    app = QGuiApplication(sys.argv[:1])
    app.setFont(QFont("Noto Sans CJK SC", 10))

    controller = ConsoleController(repo_root, app)
    QQmlEngine.setObjectOwnership(controller, QQmlEngine.CppOwnership)
    if args.profile != controller.profile:
        controller.setProfile(args.profile)

    engine = QQmlApplicationEngine()
    engine.setInitialProperties({"controller": controller})
    engine.addImportPath(str(qml_root))
    engine.loadFromModule("A1ZConsole", "Main")
    roots = engine.rootObjects()
    if not roots:
        controller.shutdown()
        return 2

    app.aboutToQuit.connect(controller.shutdown)
    if args.screenshot is not None:
        destination = args.screenshot.expanduser().resolve()

        def capture() -> None:
            destination.parent.mkdir(parents=True, exist_ok=True)
            image = roots[0].grabWindow()
            if image.isNull() or not image.save(str(destination)):
                controller._append_log(f"截图保存失败：{destination}")
            app.quit()

        QTimer.singleShot(1200, capture)
    if args.smoke_test:
        QTimer.singleShot(1500, app.quit)
    return app.exec()


if __name__ == "__main__":
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    raise SystemExit(main())
