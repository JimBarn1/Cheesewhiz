# Third-party components

The application uses Python (PSF license), Pillow 11.2.1 (HPND/Pillow license), and PySide6 / Qt 6.8.3 / Shiboken6 (Qt LGPLv3/GPL/commercial licensing, as applicable). Packaging uses PyInstaller 6.13.0 (GPL with bootloader distribution exception). Tests additionally use pytest and pypdf; these are not application runtime dependencies.

Upstream licenses and source:

- Python: https://www.python.org/psf/license/ and https://www.python.org/downloads/source/
- Pillow: https://github.com/python-pillow/Pillow/blob/11.2.1/LICENSE
- Qt for Python / Shiboken: https://code.qt.io/cgit/pyside/pyside-setup.git/ (tag v6.8.3)
- Qt: https://www.qt.io/licensing/open-source-lgpl-obligations and https://code.qt.io/
- PyInstaller: https://pyinstaller.org/en/stable/license.html

Dependency notices and source are available at the upstream links above. The application source and build files are provided so builds can be reproduced with replacement libraries. Preserve the applicable license notices when redistributing builds.
