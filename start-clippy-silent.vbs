Set WshShell = CreateObject("WScript.Shell")
' 获取脚本所在目录
strPath = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)

' 启动服务器（隐藏窗口）
WshShell.Run """" & strPath & "\server.exe""", 0, False

' 等待1秒
WScript.Sleep 1000

' 启动桌面客户端（隐藏窗口）
WshShell.Run """" & strPath & "\clippy-desktop.exe""", 0, False
