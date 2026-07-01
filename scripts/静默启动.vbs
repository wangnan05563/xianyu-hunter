' =============================================================
' Silent Startup - actual launcher (in scripts/)
' This file is invoked by the root-level 静默启动.vbs wrapper.
' It silently launches 启动服务.bat to start the XianyuHunter service.
' =============================================================

Dim WshShell, FSO, currentDir, targetBatch

Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

' 当前脚本所在目录（即 scripts/），需拼接根目录下的 启动服务.bat
currentDir = FSO.GetParentFolderName(WScript.ScriptFullName)
targetBatch = currentDir & "\启动服务.bat"

' Verify the target batch exists
If Not FSO.FileExists(targetBatch) Then
    WshShell.Popup "启动服务.bat not found!" & vbCrLf & targetBatch, _
                   10, "XianyuHunter Startup Failed", 16
    WScript.Quit 1
End If

' Launch the service batch silently (window hidden)
' 参数 0 = 隐藏窗口
WshShell.Run """" & targetBatch & """", 0, False

Set FSO = Nothing
Set WshShell = Nothing
