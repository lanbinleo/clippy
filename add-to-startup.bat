@echo off
echo 正在添加 Clippy 到开机启动...
echo.

REM 获取当前脚本所在目录
set "SCRIPT_DIR=%~dp0"

REM 创建快捷方式到启动文件夹
set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "VBS_PATH=%SCRIPT_DIR%start-clippy-silent.vbs"

REM 使用 PowerShell 创建快捷方式
powershell -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%STARTUP_FOLDER%\Clippy.lnk'); $Shortcut.TargetPath = '%VBS_PATH%'; $Shortcut.WorkingDirectory = '%SCRIPT_DIR%'; $Shortcut.Description = 'Clippy 多端同步剪贴板'; $Shortcut.Save()"

echo.
echo 成功！Clippy 已添加到开机启动
echo 快捷方式位置: %STARTUP_FOLDER%\Clippy.lnk
echo.
pause
