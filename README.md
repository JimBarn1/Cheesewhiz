# Image to PDF

Offline Windows desktop image-to-PDF converter with thumbnails, natural sorting, manual ordering, original/A4/Letter pages and background conversion.

## Download

[**Download the complete source ZIP**](https://github.com/JimBarn1/Cheesewhiz/raw/refs/heads/main/downloads/ImageToPDF-Source-and-Windows-Build.zip)

The ZIP includes source, tests, a preview, a sample PDF and a double-click Windows build script. Extract it and read `ImageToPDF/README.md`.

## Windows executable

[**Download the successfully built Windows EXE artifact**](https://github.com/JimBarn1/Cheesewhiz/actions/runs/43157356076/artifacts/13916402484) (GitHub sign-in may be required). Extract the download and double-click `ImageToPDF.exe`. All 15 automated tests passed on Windows; manual desktop acceptance checks remain.

Open [Actions → Build Windows portable application](https://github.com/JimBarn1/Cheesewhiz/actions/workflows/image-to-pdf-windows.yml), click **Run workflow**, and wait for a successful run. Download its **ImageToPDF-Windows-x64** artifact and extract `ImageToPDF.exe`. End users do not need Python or internet access.

The workflow runs the automated tests on Windows before building. A successful build does not replace manual Windows 10/11 desktop acceptance checks.

## Source and local build

The project is in [`ImageToPDF/`](ImageToPDF/). On a Windows build machine with Python 3.12 x64 installed, double-click `ImageToPDF/build-windows.bat`.

See the [full README](ImageToPDF/README.md) and [test report](ImageToPDF/TEST-REPORT.md) for behavior, quality settings and validation details.
