"""Image to PDF — portable, offline desktop application."""
import io
import sys
from pathlib import Path
from PIL import Image, ImageOps
from PySide6.QtCore import Qt, QThread, Signal, QSize, QUrl
from PySide6.QtGui import QIcon, QPixmap, QDesktopServices
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QLineEdit, QCheckBox, QComboBox,
    QListWidget, QListWidgetItem, QAbstractItemView, QFileDialog, QMessageBox,
    QProgressBar, QGroupBox, QFormLayout, QTextEdit, QDialog, QDialogButtonBox)
from engine import discover, convert, natural_key, Options, Cancelled


class ScanThread(QThread):
    batch = Signal(object)
    result = Signal(object)
    failed = Signal(str)
    def __init__(self, folder, recursive):
        super().__init__()
        self.folder, self.recursive = folder, recursive
    def run(self):
        try:
            paths, warnings = discover(self.folder, self.recursive, self.isInterruptionRequested)
            batch = []
            for path in paths:
                if self.isInterruptionRequested():
                    raise Cancelled()
                try:
                    with Image.open(path) as source:
                        source.seek(0)
                        source.thumbnail((96, 72))
                        thumb = ImageOps.exif_transpose(source).convert('RGBA')
                        data = io.BytesIO()
                        thumb.save(data, 'PNG')
                        batch.append((str(path), data.getvalue()))
                except Exception as error:
                    warnings.append(f'{path}: {error}')
                if len(batch) == 32:
                    self.batch.emit(batch)
                    batch = []
            if batch:
                self.batch.emit(batch)
            self.result.emit(warnings)
        except Cancelled:
            self.result.emit(['Folder scan cancelled.'])
        except Exception as error:
            self.failed.emit(str(error))


class ConvertThread(QThread):
    progress = Signal(int, int)
    result = Signal(int, object)
    failed = Signal(str)
    cancelled = Signal()
    def __init__(self, paths, target, options):
        super().__init__()
        self.paths, self.target, self.options = paths, target, options
    def run(self):
        try:
            count, skipped = convert(self.paths, self.target, self.options,
                                     self.progress.emit, self.isInterruptionRequested)
            self.result.emit(count, skipped)
        except Cancelled:
            self.cancelled.emit()
        except Exception as error:
            self.failed.emit(str(error))


STYLE = '''
QWidget { font-family: "Segoe UI", "DejaVu Sans"; font-size: 10pt; color: #23324a; }
QMainWindow, QDialog { background: #f3f6fb; }
QGroupBox { background: white; border: 1px solid #dce3ef; border-radius: 10px;
 padding: 18px 14px 12px; margin-top: 12px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 15px; padding: 0 5px; }
QLineEdit, QComboBox { background: white; border: 1px solid #cbd5e3;
 border-radius: 6px; padding: 8px; min-height: 18px; }
QPushButton { background: #e7edf7; border: 1px solid #cbd5e3; border-radius: 6px;
 padding: 9px 16px; font-weight: 600; }
QPushButton:hover { background: #d9e5f8; }
QPushButton:focus, QLineEdit:focus, QComboBox:focus { border: 2px solid #2563eb; }
QPushButton:disabled { background: #edf0f5; color: #8c98ab; }
QPushButton#convert { background: #2563eb; color: white; border: none;
 padding: 15px; font-size: 12pt; }
QPushButton#convert:hover { background: #1d4ed8; }
QPushButton#convert:disabled { background: #a4bce9; }
QListWidget { border: 1px solid #dce3ef; border-radius: 7px; background: white; padding: 5px; }
QListWidget::item { padding: 5px; border-bottom: 1px solid #edf1f7; }
QListWidget::item:selected { background: #e2ecff; color: #1640a0; }
QProgressBar { border: none; border-radius: 5px; background: #e1e8f3; height: 10px; text-align: center; }
QProgressBar::chunk { background: #2563eb; border-radius: 5px; }
QCheckBox { spacing: 8px; }
QLabel#subtitle { color: #63738b; }
'''


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.last_pdf = None
        self.warnings = []
        self.setWindowTitle('Image to PDF')
        self.resize(1000, 860)
        self.setMinimumSize(760, 660)
        self.setAcceptDrops(True)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(12)
        title = QLabel('Image to PDF')
        title.setStyleSheet('font-size: 26pt; font-weight: 700;')
        layout.addWidget(title)
        subtitle = QLabel('Your images. One beautifully ordered PDF.   •   Works entirely offline')
        subtitle.setObjectName('subtitle')
        layout.addWidget(subtitle)
        self.input_group = QGroupBox('1   Choose your images')
        inputs = QVBoxLayout(self.input_group)
        row = QHBoxLayout()
        self.folder = QLineEdit()
        self.folder.setPlaceholderText('Drop a folder here, or browse…')
        self.folder.setAccessibleName('Image folder')
        self.browse = QPushButton('Browse Folder')
        self.browse.clicked.connect(self.choose_folder)
        self.folder.returnPressed.connect(self.scan)
        row.addWidget(self.folder, 1)
        row.addWidget(self.browse)
        inputs.addLayout(row)
        row = QHBoxLayout()
        self.recursive = QCheckBox('Include subfolders')
        self.recursive.toggled.connect(lambda: self.scan() if self.folder.text() else None)
        self.rescan = QPushButton('Refresh')
        self.rescan.clicked.connect(self.scan)
        row.addWidget(self.recursive)
        row.addStretch()
        row.addWidget(self.rescan)
        inputs.addLayout(row)
        layout.addWidget(self.input_group)
        row = QHBoxLayout()
        self.counter = QLabel('0 Images Found')
        self.counter.setStyleSheet('font-weight: 600;')
        row.addWidget(self.counter)
        row.addStretch()
        row.addWidget(QLabel('Order'))
        self.sort = QComboBox()
        self.sort.addItems(['A–Z (natural)', 'Z–A (natural)', 'Manual order'])
        self.sort.currentIndexChanged.connect(self.sort_images)
        row.addWidget(self.sort)
        layout.addLayout(row)
        self.images = QListWidget()
        self.images.setAccessibleName('Images in PDF page order')
        self.images.setIconSize(QSize(96, 72))
        self.images.setUniformItemSizes(True)
        self.images.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.images.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.images.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.images.model().rowsMoved.connect(self.manual_order)
        layout.addWidget(self.images, 1)
        row = QHBoxLayout()
        hint = QLabel('Drag rows or use the arrows to rearrange pages.')
        hint.setObjectName('subtitle')
        row.addWidget(hint)
        row.addStretch()
        self.up = QPushButton('↑ Move up')
        self.down = QPushButton('↓ Move down')
        self.up.clicked.connect(lambda: self.move(-1))
        self.down.clicked.connect(lambda: self.move(1))
        row.addWidget(self.up)
        row.addWidget(self.down)
        layout.addLayout(row)
        self.output_group = QGroupBox('2   Set up your PDF')
        form = QFormLayout(self.output_group)
        self.page_size = QComboBox()
        self.page_size.addItems(['Original image dimensions', 'A4 — automatic orientation', 'US Letter — automatic orientation'])
        form.addRow('Page size', self.page_size)
        self.compression = QCheckBox('Smaller file (JPEG quality 85; may reduce image quality)')
        form.addRow('', self.compression)
        self.destination = QLineEdit()
        self.destination.setPlaceholderText('Choose where to save your PDF…')
        self.destination.setAccessibleName('Output PDF path')
        self.save_button = QPushButton('Save As…')
        self.save_button.clicked.connect(self.choose_output)
        output_row = QHBoxLayout()
        output_row.addWidget(self.destination, 1)
        output_row.addWidget(self.save_button)
        form.addRow('Save to', output_row)
        layout.addWidget(self.output_group)
        self.convert_button = QPushButton('Convert to PDF')
        self.convert_button.setObjectName('convert')
        self.convert_button.clicked.connect(self.start_conversion)
        self.convert_button.setEnabled(False)
        layout.addWidget(self.convert_button)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)
        row = QHBoxLayout()
        self.status = QLabel('Select a folder to get started.')
        self.status.setWordWrap(True)
        self.details = QPushButton('View details')
        self.details.hide()
        self.details.clicked.connect(self.show_details)
        self.open_button = QPushButton('Open PDF')
        self.open_button.hide()
        self.open_button.clicked.connect(self.open_pdf)
        self.cancel_button = QPushButton('Cancel')
        self.cancel_button.hide()
        self.cancel_button.clicked.connect(self.cancel)
        row.addWidget(self.status, 1)
        row.addWidget(self.details)
        row.addWidget(self.open_button)
        row.addWidget(self.cancel_button)
        layout.addLayout(row)

    def busy(self):
        return self.worker is not None

    def set_busy(self, value):
        for widget in (self.input_group, self.sort, self.images, self.up, self.down, self.output_group):
            widget.setEnabled(not value)
        self.convert_button.setEnabled(not value and self.images.count() > 0)
        self.cancel_button.setVisible(value)
        self.cancel_button.setEnabled(True)
        if value:
            self.open_button.hide()
            self.details.hide()
            self.warnings = []

    def attach(self, worker):
        self.worker = worker
        worker.finished.connect(self.worker_finished)
        self.set_busy(True)
        worker.start()

    def worker_finished(self):
        worker = self.worker
        self.worker = None
        self.set_busy(False)
        worker.deleteLater()

    def choose_folder(self):
        path = QFileDialog.getExistingDirectory(self, 'Choose an image folder', self.folder.text())
        if path:
            self.folder.setText(path)
            self.scan()

    def scan(self):
        if self.busy():
            return
        folder = Path(self.folder.text().strip()).expanduser()
        if not folder.is_dir():
            QMessageBox.warning(self, 'Folder not found', 'Choose an existing image folder.')
            return
        self.folder.setText(str(folder.absolute()))
        self.images.clear()
        self.counter.setText('Scanning…')
        self.progress.setRange(0, 0)
        self.status.setText('Finding images and preparing thumbnails…')
        if not self.destination.text():
            self.destination.setText(str(folder / f'{folder.name or "Images"}.pdf'))
        worker = ScanThread(str(folder), self.recursive.isChecked())
        worker.batch.connect(self.add_batch)
        worker.result.connect(self.scan_done)
        worker.failed.connect(self.error)
        self.attach(worker)

    def add_batch(self, batch):
        for path, data in batch:
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            p = Path(path)
            try:
                name = str(p.relative_to(Path(self.folder.text())))
            except ValueError:
                name = p.name
            item = QListWidgetItem(QIcon(pixmap), name)
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(path)
            item.setSizeHint(QSize(0, 84))
            self.images.addItem(item)
        self.counter.setText(f'{self.images.count():,} Images Found')

    def scan_done(self, warnings):
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.warnings = warnings
        self.details.setVisible(bool(warnings))
        self.sort_images()
        count = self.images.count()
        self.counter.setText(f'{count:,} Images Found')
        self.status.setText(f'Ready. {len(warnings)} unreadable files or scan warnings.' if warnings else 'Ready to convert. Each image becomes one page.')
        if not count:
            self.status.setText('No readable images found. Try another folder or include subfolders.')
            QMessageBox.information(self, 'No images found', 'No readable supported images were found in this folder.\nSupported: PNG, JPG, JPEG, WEBP, BMP, TIFF and GIF.')

    def sort_images(self):
        if self.sort.currentIndex() == 2:
            return
        selected = self.images.currentItem()
        items = [self.images.takeItem(0) for _ in range(self.images.count())]
        items.sort(key=lambda item: natural_key(item.data(Qt.ItemDataRole.UserRole)), reverse=self.sort.currentIndex() == 1)
        for item in items:
            self.images.addItem(item)
        if selected:
            self.images.setCurrentItem(selected)

    def manual_order(self, *args):
        self.sort.setCurrentIndex(2)

    def move(self, delta):
        row = self.images.currentRow()
        target = row + delta
        if row >= 0 and 0 <= target < self.images.count():
            item = self.images.takeItem(row)
            self.images.insertItem(target, item)
            self.images.setCurrentRow(target)
            self.manual_order()

    def choose_output(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Save PDF', self.destination.text(), 'PDF documents (*.pdf)', options=QFileDialog.Option.DontConfirmOverwrite)
        if path:
            if not path.lower().endswith('.pdf'):
                path += '.pdf'
            self.destination.setText(path)

    def start_conversion(self):
        if self.busy() or not self.images.count():
            return
        if not self.destination.text().strip():
            self.choose_output()
            if not self.destination.text().strip():
                return
        target = Path(self.destination.text().strip()).expanduser().absolute()
        if target.suffix.lower() != '.pdf':
            QMessageBox.warning(self, 'PDF filename required', 'Choose an output filename ending in .pdf.')
            return
        if not target.parent.is_dir() or target.is_dir():
            QMessageBox.warning(self, 'Invalid destination', 'Choose a PDF filename in an existing writable folder.')
            return
        overwrite = target.exists()
        if overwrite and QMessageBox.question(self, 'Replace existing PDF?', f'{target.name} already exists.\nReplace it?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        paths = [self.images.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.images.count())]
        options = Options(['original', 'a4', 'letter'][self.page_size.currentIndex()], self.compression.isChecked(), overwrite)
        worker = ConvertThread(paths, target, options)
        worker.progress.connect(self.conversion_progress)
        worker.result.connect(self.conversion_done)
        worker.failed.connect(self.error)
        worker.cancelled.connect(self.conversion_cancelled)
        self.last_pdf = str(target)
        self.progress.setRange(0, len(paths))
        self.progress.setValue(0)
        self.status.setText('Creating your PDF…')
        self.attach(worker)

    def conversion_progress(self, done, total):
        self.progress.setValue(done)
        self.status.setText(f'Processing image {done:,} of {total:,}…')

    def conversion_done(self, count, skipped):
        self.warnings = [f'{path}: {error}' for path, error in skipped]
        self.details.setVisible(bool(skipped))
        self.progress.setValue(self.progress.maximum())
        self.status.setText(f'PDF saved successfully — {count:,} pages.' + (f' {len(skipped)} files skipped; see details.' if skipped else ''))
        self.open_button.show()

    def error(self, message):
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.status.setText('Unable to complete the operation.')
        QMessageBox.critical(self, 'Image to PDF', message)

    def conversion_cancelled(self):
        self.progress.setValue(0)
        self.status.setText('Cancelled. No output PDF was changed.')

    def cancel(self):
        if self.worker:
            self.worker.requestInterruption()
            self.cancel_button.setEnabled(False)
            self.status.setText('Cancelling after the current image…')

    def show_details(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Files skipped and warnings')
        dialog.resize(700, 380)
        layout = QVBoxLayout(dialog)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText('\n\n'.join(self.warnings))
        layout.addWidget(text)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def open_pdf(self):
        if self.last_pdf and not QDesktopServices.openUrl(QUrl.fromLocalFile(self.last_pdf)):
            QMessageBox.warning(self, 'Could not open PDF', 'No PDF viewer could be opened. Your PDF is saved at:\n' + self.last_pdf)

    def dragEnterEvent(self, event):
        urls = event.mimeData().urls()
        if not self.busy() and len(urls) == 1 and urls[0].isLocalFile() and Path(urls[0].toLocalFile()).is_dir():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not self.busy() and len(urls) == 1 and Path(urls[0].toLocalFile()).is_dir():
            self.folder.setText(urls[0].toLocalFile())
            self.scan()
            event.acceptProposedAction()

    def closeEvent(self, event):
        if self.busy():
            QMessageBox.information(self, 'Operation in progress', 'Use Cancel and wait for the operation to finish before closing.')
            event.ignore()
        else:
            event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('Image to PDF')
    app.setOrganizationName('ImageToPDF')
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    window = Window()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
