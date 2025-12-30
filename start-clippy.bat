@echo off
REM Clippy 启动脚本
echo 正在启动 Clippy...

REM 启动服务器（后台运行）
start /B "" "%~dp0server.exe"

REM 等待1秒让服务器启动
timeout /t 1 /nobreak >nul

REM 启动桌面客户端（后台运行）
start /B "" "%~dp0clippy-desktop.exe"

echo Clippy 已启动！
echo 服务器运行在 localhost:8948
echo 桌面客户端已最小化到系统托盘
exit
