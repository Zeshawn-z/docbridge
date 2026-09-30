"""Generic background runner. No feature branches or widget references."""
from PySide6.QtCore import QThread, Signal


class ConversionWorker(QThread):
    file_started = Signal(str)
    file_result = Signal(str, object)
    file_error = Signal(str, str)
    batch_done = Signal(int, int, int, bool)
    log_message = Signal(str)

    def __init__(self, files, output, overwrite, convert, settings, parent=None):
        super().__init__(parent)
        self.files = tuple(files)
        self.output, self.overwrite = output, overwrite
        self.convert, self.settings = convert, settings

    def run(self):
        success = failed = 0
        for path in self.files:
            if self.isInterruptionRequested():
                break
            self.file_started.emit(str(path))
            try:
                result = self.convert(path, self.output, self.overwrite, self.settings,
                                      lambda line: self.log_message.emit(str(line)))
                success += 1
                self.file_result.emit(str(path), result)
            except Exception as exc:
                failed += 1
                self.file_error.emit(str(path), str(exc))
        self.batch_done.emit(success, failed, len(self.files), self.isInterruptionRequested())
