"""Start the app:  python -m crkit_app"""
import sys


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("PySide6 is not installed. Run:  pip install -r requirements.txt")
        return 1
    from .main_window import MainWindow, STYLE

    app = QApplication(sys.argv)
    app.setApplicationName("CR-TEST Contact Resistance Recorder")
    app.setStyleSheet(STYLE)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
