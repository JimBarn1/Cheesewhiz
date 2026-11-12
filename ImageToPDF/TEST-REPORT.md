# Validation report

## Actual environment and results

- Platform: Linux x86_64, Python 3.12.14.
- Runtime dependencies: PySide6 6.8.3, Pillow 11.2.1.
- `python -m pytest -q`: **15 passed in 0.85 seconds**.
- The actual PDF writer is exercised; generated PDFs are parsed with pypdf in strict mode and embedded image pixels and dimensions are checked.
- A generated four-page A4 PDF was rendered successfully with Poppler (`pdftoppm`). The first rendered page and the desktop interface screenshot were visually inspected.
- A single-file **Linux** application was built successfully from `ImageToPDF.spec` with PyInstaller 6.13.0. Its bundled GUI remained running after a four-second offscreen launch, with no application traceback. This checks packaging on Linux only.

## Automated coverage

1. Natural sorting of `1.png`, `2.png`, `10.png`, `100.png`, `Page 2.png`, `Page 10.png`; optional recursive discovery and ignored text files.
2. All requested image formats, including both TIFF extensions, with corrupt input, first-frame GIF and first-page multipage TIFF.
3. Forward and reverse ordering verified by extracting each PDF page's actual pixels; a custom manual order is also checked.
4. Original-size, A4 and US Letter page dimensions and aspect-preserving drawing matrices.
5. EXIF orientation and alpha compositing onto white.
6. Byte-identical JPEG embedding in the default quality mode.
7. Optional JPEG encoding retains pixel dimensions.
8. A 125-image folder: every PDF page, natural order, image dimensions and final progress count.
9. Existing-file protection, confirmed replacement, cancellation and temporary-file cleanup.
10. Empty and all-corrupt input produce no output PDF.
11. An existing file appearing during conversion is not overwritten without authorization.
12. Qt GUI integration: background scanning with the event loop active, thumbnail rows, reverse sort, manual move, conversion in displayed order, success status and Open PDF button.

The parameterized cases make 15 test executions in total. Test-generated images are synthetic; this is not a benchmark for gigapixel files or thousands of high-resolution photos.

## Not verified here

A Windows x64 executable was built successfully on GitHub Actions (run 43157356076) with Python 3.12.10; all 15 automated tests passed on Windows in 1.87 seconds. The built EXE was not interactively launched or tested on a Windows desktop. Windows-specific Explorer drag-and-drop, native file dialogs, PDF viewer launch, file locking, SmartScreen behavior, Unicode/long-path policy and clean-machine portability need the Windows acceptance checks in the README. The GitHub Actions Windows build succeeded and uploaded artifact 13916402484. Offscreen GUI tests exercise application logic but do not establish Windows desktop integration.

The default page-size limit is 200 inches. Individual decoded image memory still depends on image dimensions. Non-RGB and high bit depth source formats are normalized to 8-bit RGB, and embedded ICC profiles are not preserved as PDF output intents. See the README for quality and format details.
