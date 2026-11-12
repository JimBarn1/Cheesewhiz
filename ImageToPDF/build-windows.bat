@echo off
setlocal
cd /d "%~dp0"
echo Building Image to PDF for Windows 10/11 x64...
where py >nul 2>nul
if errorlevel 1 goto nopython
py -3.12 -m venv .venv
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pytest -q
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm ImageToPDF.spec
if errorlevel 1 goto failed
powershell -NoProfile -Command "Compress-Archive -Path 'dist\ImageToPDF.exe','README.md','THIRD-PARTY-NOTICES.md' -DestinationPath 'dist\ImageToPDF-Windows-x64.zip' -Force"
if errorlevel 1 goto failed
echo.
echo SUCCESS: dist\ImageToPDF.exe and dist\ImageToPDF-Windows-x64.zip
echo Double-click the EXE to start. End users do not need Python.
pause
exit /b 0
:nopython
echo Install Python 3.12 x64 from python.org with the Python launcher, then retry.
goto failed
:failed
echo BUILD FAILED. Read the error above. No successful Windows build is claimed.
pause
exit /b 1
