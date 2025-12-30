@echo off
echo Packaging Clippy Desktop...
pyinstaller --onefile --windowed --name=clippy-desktop --icon=NONE desktop.py
echo.
echo Packaging complete!
echo Executable located at: dist\clippy-desktop.exe
pause
