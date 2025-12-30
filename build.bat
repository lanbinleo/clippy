@echo off
echo 正在打包 Clippy Desktop...
pyinstaller --onefile --windowed --name=clippy-desktop --icon=NONE desktop.py
echo.
echo 打包完成！
echo 可执行文件位于: dist\clippy-desktop.exe
pause
