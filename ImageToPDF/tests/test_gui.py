import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import time
from pathlib import Path
from PIL import Image
from pypdf import PdfReader
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from app import Window, STYLE


def wait(app, window):
    deadline = time.monotonic() + 30
    ticks = 0
    while window.busy():
        app.processEvents()
        time.sleep(.005)
        ticks += 1
        assert time.monotonic() < deadline
    app.processEvents()
    return ticks


def test_gui_scan_sort_manual_convert_and_success(tmp_path):
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(STYLE)
    for name, width in [('10.png', 100), ('2.png', 20), ('1.png', 10)]:
        Image.new('RGB', (width, 30), 'red').save(tmp_path / name)
    window = Window()
    window.show()
    window.folder.setText(str(tmp_path))
    window.scan()
    assert wait(app, window) > 0
    assert window.images.count() == 3
    assert [window.images.item(i).text() for i in range(3)] == ['1.png', '2.png', '10.png']
    window.sort.setCurrentIndex(1)
    assert window.images.item(0).text() == '10.png'
    window.images.setCurrentRow(0)
    window.move(1)
    assert window.sort.currentIndex() == 2
    assert [window.images.item(i).text() for i in range(3)] == ['2.png', '10.png', '1.png']
    dest = tmp_path / 'gui.pdf'
    window.destination.setText(str(dest))
    window.start_conversion()
    assert wait(app, window) > 0
    assert [p.images[0].image.width for p in PdfReader(dest).pages] == [20, 100, 10]
    assert 'successfully' in window.status.text()
    assert not window.open_button.isHidden()
    assert window.convert_button.isEnabled()
    window.close()
