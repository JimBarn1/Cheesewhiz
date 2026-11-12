# Image to PDF

An offline desktop application for combining a folder of images into a naturally ordered PDF. Designed for Windows 10 and Windows 11, x64.

**Delivery status:** Source, automated tests, build specification, Windows build script and GitHub Actions workflow are included. Development and testing took place on Linux. No Windows `.exe` was produced or tested in this environment. A Linux PyInstaller build was created as a packaging check; it is not a Windows executable. Follow the Windows build steps below to create the portable application.

## Use the application

1. Double-click `ImageToPDF.exe` after building on Windows. No Python installation or internet connection is needed by end users.
2. Choose **Browse Folder**, or drag one folder onto the window. Enable **Include subfolders** if needed. Scanning and thumbnails run in the background.
3. Check the displayed list. **A–Z (natural)** places `1.png`, `2.png`, `10.png`, `100.png` in that order. **Z–A** reverses it. Drag rows, or select a row and use **Move up / Move down**, for manual ordering. The PDF follows this displayed order exactly.
4. Choose page size and the output PDF location. A default filename in the selected folder is supplied.
5. Click **Convert to PDF**. When finished, click **Open PDF** to open it using your default PDF viewer.

The application accepts PNG, JPG/JPEG, WEBP, BMP, TIF/TIFF and GIF. Animated formats and multipage TIFFs contribute **only their first frame**: one input file equals one PDF page. Files with other extensions are ignored. Unreadable images are skipped with details. Refresh the folder after adding or changing files.

### Page size and quality

- **Original image dimensions:** Image pixels and available DPI metadata determine physical page size. Missing, malformed or implausible DPI values use 96 DPI. Very large physical pages are proportionally limited to 200 inches for PDF compatibility. Pixel resolution is retained.
- **A4 / US Letter:** Landscape images get landscape pages; portrait and square images get portrait pages. Images are centered and fit inside the page without cropping or stretching. White space may remain.
- **Default quality:** Compatible RGB/grayscale JPEGs are embedded byte for byte. Other images use lossless RGB/grayscale encoding. EXIF rotation is honored. Transparency is flattened onto white; palette, CMYK and high bit depth images are converted to standard 8-bit RGB. This preserves normal viewing quality, but is not an archival color-managed workflow.
- **Smaller file:** Encodes each image as JPEG quality 85 without reducing pixel dimensions. This is lossy and is usually smaller for photographs; it can be larger than lossless encoding for simple graphics.

Images are processed one file at a time. Thousands of compressed page streams are not retained in memory, although one large decoded image and the thumbnail list require memory. Extremely large images may be rejected by Pillow's image-size protections. Folder junctions and directory symlinks are not followed. Equal filenames in subfolders use deterministic path tie-breakers. Sorting is case-insensitive and numeric; it is not Windows Explorer's locale-specific collation.

### Errors and cancellation

Existing PDFs require explicit replacement confirmation. The app writes to a temporary file in the destination folder and publishes only a completed PDF. Cancellation, all-corrupt input or a failed conversion removes the temporary output and leaves an existing PDF intact. Cancellation is checked between image-processing steps; decoding one large image can delay it. Close the application after the operation completes or cancellation finishes.

Use **View details** for unreadable files and scan warnings. If a folder has no readable images, select another folder or include subfolders. For a write error, choose a writable local folder and check disk space. If a PDF is open in another Windows program, close it before replacing it. If no PDF viewer is installed, use File Explorer to find the saved PDF and open it later.

## Build a portable Windows EXE

Only the **build machine** needs Python and internet access. The finished EXE includes the Python runtime, Qt and Pillow, and runs offline without separate software installation.

1. On Windows 10/11 x64, install **Python 3.12 x64** from python.org, including the **Python launcher** (`py`). Python 3.12.10 is a suitable Windows installer release.
2. Extract this project ZIP to a local folder. Keep `app.py`, `engine.py`, the requirements files and `ImageToPDF.spec` together.
3. Double-click **`build-windows.bat`**. No commands need to be typed. It creates an isolated build environment, installs pinned direct dependencies, runs tests and builds with PyInstaller. It pauses so errors remain visible.
4. Successful output:
   - `dist\ImageToPDF.exe` — single portable executable.
   - `dist\ImageToPDF-Windows-x64.zip` — executable, README and dependency notices.
5. Copy the EXE or application ZIP to an otherwise clean Windows 10/11 x64 computer. Double-click the EXE and perform the manual acceptance checks below before distributing it.

For developers, the equivalent commands in a terminal opened in the project folder are:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm ImageToPDF.spec
```

PyInstaller must run on Windows to produce a Windows EXE. Renaming the Linux bundle to `.exe` does not work. The single-file build extracts runtime libraries into the user's temporary folder at launch, so the first launch can take several seconds. It requires no administrator privileges. The build is unsigned; Windows may show a publisher/SmartScreen prompt. Code signing is not included.

### Automated Windows build option

The included `.github/workflows/build-windows.yml` runs on `windows-2022`. Upload the project to your own GitHub repository, enable Actions, and run **Build Windows portable application** from the Actions tab. Download the `ImageToPDF-Windows-x64` artifact after a successful run. A version tag such as `v1.0.0` also triggers the workflow. This workflow is supplied but was **not executed** during this delivery.

### Run from source

Install `requirements.txt` in a Python 3.12 virtual environment, then run `python app.py`. This is a developer option; end users should use the built EXE. GUI testing on Linux uses Qt's offscreen platform; Windows shell dialogs, drag-and-drop integration and default-viewer launch still require manual checks on Windows.

## Project contents

- `app.py`: PySide6 GUI, background scan/conversion workers, thumbnails, ordering and progress.
- `engine.py`: natural sorting, discovery, image normalization and streaming PDF writer.
- `tests/`: PDF correctness, ordering, formats, error handling, cancellation, large folder and GUI integration tests.
- `ImageToPDF.spec`: PyInstaller single-executable configuration.
- `build-windows.bat`: double-click Windows build.
- `.github/workflows/build-windows.yml`: Windows CI build and artifacts.
- `TEST-REPORT.md`: actual validation and remaining Windows checks.
- `preview.png`, `sample.pdf`: interface preview and example four-page output.

## Manual Windows acceptance checks

Run the built EXE on Windows 10 and Windows 11 without Python installed, with networking disabled. Browse and drag a folder, toggle recursion, check thumbnail scrolling and sort order, rearrange rows with mouse and keyboard buttons, save to a Unicode path, reject and accept overwrite confirmation, cancel a large conversion, open the final PDF, and verify helpful messages for unreadable files, read-only destinations and output locked by another application. Include a 100+ image folder and inspect PDF page order and orientation in a Windows PDF viewer.
