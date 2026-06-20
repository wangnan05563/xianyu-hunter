' =============================================================
' 闲鱼猎手 - 静默启动（推荐方式，无黑框）
' 双击此文件即可启动服务并打开浏览器
' 错误捕获与日志记录写入 logs\startup.log
' =============================================================

Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

' 切换到脚本所在目录
strDir = FSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strDir

' 确保 logs 目录存在
strLogDir = strDir & "\logs"
If Not FSO.FolderExists(strLogDir) Then
    FSO.CreateFolder(strLogDir)
End If

strLogFile = strLogDir & "\startup.log"

' 日志写入辅助函数
Sub WriteLog(msg)
    On Error Resume Next
    Set f = FSO.OpenTextFile(strLogFile, 8, True)
    f.WriteLine Now() & " [VBS] " & msg
    f.Close
    On Error GoTo 0
End Sub

WriteLog "=== 静默启动开始 ==="

' 清理残留 WebView2 进程（避免端口/文件锁冲突）
On Error Resume Next
WshShell.Run "taskkill /F /IM msedgewebview2.exe", 0, True
If Err.Number <> 0 Then
    WriteLog "清理 WebView2 进程时出错（可忽略）: " & Err.Description
    Err.Clear
End If
On Error GoTo 0

' 检查 .venv 是否存在
strVenv = strDir & "\.venv\Scripts\python.exe"
If Not FSO.FileExists(strVenv) Then
    WriteLog "[ERROR] .venv 未找到，请先运行: python -m venv .venv"
    WshShell.Popup ".venv 未找到！" & vbCrLf & _
                   "请先运行: python -m venv .venv" & vbCrLf & _
                   "然后: .venv\Scripts\pip install -r requirements.txt", _
                   10, "XianyuHunter 启动失败", 16
    WScript.Quit 1
End If

' 检查启动服务.bat 是否存在
strBat = strDir & "\启动服务.bat"
If Not FSO.FileExists(strBat) Then
    WriteLog "[ERROR] 启动服务.bat 未找到: " & strBat
    WScript.Quit 1
End If

WriteLog "调用 启动服务.bat ..."

' 以隐藏窗口模式启动 bat（无黑框）
' 第二个参数 0 = 隐藏窗口, False = 不等待完成
On Error Resume Next
WshShell.Run "cmd /c """ & strBat & """", 0, False
If Err.Number <> 0 Then
    WriteLog "[ERROR] 启动 启动服务.bat 失败: " & Err.Description
    WshShell.Popup "启动服务失败！" & vbCrLf & _
                   "错误: " & Err.Description & vbCrLf & _
                   "请查看 logs\startup.log", _
                   10, "XianyuHunter 启动失败", 16
    Err.Clear
    WScript.Quit 1
End If
On Error GoTo 0

WriteLog "启动服务.bat 已在后台执行"

' 等待 Web 服务就绪（最多 40 秒）
bWebReady = False
For i = 1 To 20
    WScript.Sleep 2000
    On Error Resume Next
    Set http = CreateObject("WinHttp.WinHttpRequest.5.1")
    http.SetTimeouts 2000, 2000, 2000, 2000
    http.Open "GET", "http://127.0.0.1:8000/api/auth/me", False
    http.Send
    If Err.Number = 0 Then
        If http.Status = 200 Or http.Status = 401 Then
            bWebReady = True
            WriteLog "Web 服务已就绪 (HTTP " & http.Status & ")"
            Exit For
        End If
    End If
    Err.Clear
    On Error GoTo 0
Next

If Not bWebReady Then
    WriteLog "[WARN] Web 服务未在 40 秒内就绪，仍尝试打开浏览器"
End If

' 打开浏览器
On Error Resume Next
WshShell.Run "http://127.0.0.1:8000/app/"
If Err.Number <> 0 Then
    WriteLog "[ERROR] 打开浏览器失败: " & Err.Description
    Err.Clear
End If
On Error GoTo 0

WriteLog "=== 静默启动完成 ==="

Set FSO = Nothing
Set WshShell = Nothing
