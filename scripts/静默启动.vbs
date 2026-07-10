' =============================================================
' 静默启动 - 实际启动器（位于 scripts/）
' 此文件由根目录的 静默启动.vbs 包装器调用
' 静默启动 启动服务.bat 以启动闲鱼猎人服务
' =============================================================

Dim WshShell, FSO, currentDir, targetBatch

Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

' 当前脚本所在目录（即 scripts/），需拼接根目录下的 启动服务.bat
currentDir = FSO.GetParentFolderName(WScript.ScriptFullName)
targetBatch = currentDir & "\启动服务.bat"

' 验证目标批处理文件是否存在
If Not FSO.FileExists(targetBatch) Then
    WshShell.Popup "未找到 启动服务.bat！" & vbCrLf & targetBatch, _
                   10, "闲鱼猎人启动失败", 16
    WScript.Quit 1
End If

' 静默启动服务批处理（隐藏窗口）
' 参数 0 = 隐藏窗口
WshShell.Run """" & targetBatch & """", 0, False

Set FSO = Nothing
Set WshShell = Nothing
