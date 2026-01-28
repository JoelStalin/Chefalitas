@echo off
REM Build Local Printer Agent (onedir). Run from installer dir.
REM Requires: pip install pyinstaller pywin32
REM Usage: build.bat [TOKEN]
set TOKEN=%~1
if "%TOKEN%"=="" set TOKEN=REPLACE_ME
cd /d "%~dp0"
cd ..
python -m pip install pyinstaller pywin32 --quiet
if not exist build mkdir build
if not exist dist mkdir dist
python -m PyInstaller --clean --noconfirm installer\pyinstaller.spec
echo Built. Output in dist\LocalPrinterAgent\
echo To generate config with token, create ProgramData\PosPrintingSuite\LocalPrinterAgent\config.json with key "token": "%TOKEN%"
exit /b 0
