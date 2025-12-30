@echo off
echo 正在从开机启动移除 Clippy...
echo.

set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT_PATH=%STARTUP_FOLDER%\Clippy.lnk"

if exist "%SHORTCUT_PATH%" (
    del "%SHORTCUT_PATH%"
    echo 成功移除！
) else (
    echo Clippy 不在开机启动中
)

echo.
pause
