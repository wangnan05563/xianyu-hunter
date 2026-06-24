' =============================================================
' Silent Startup - starts service in background, no console window
' Located in scripts/ directory, double-click to launch
' All errors are logged to logs\startup.log
' =============================================================

Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

' Resolve paths: scripts/ -> project root
strScriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)
strDir = FSO.GetParentFolderName(strScriptDir)
WshShell.CurrentDirectory = strDir

strLogDir = strDir & "\logs"
strLogFile = strLogDir & "\startup.log"
strWebLog = strLogDir & "\web.log"
strPidFile = strLogDir & "\web.pid"
strVenv = strDir & "\.venv\Scripts\python.exe"
strTempFile = FSO.GetSpecialFolder(2) & "\xianyu_netstat.txt"

' Ensure logs directory exists
If Not FSO.FolderExists(strLogDir) Then
    FSO.CreateFolder strLogDir
End If

' --- Helpers ---

Sub WriteLog(msg)
    On Error Resume Next
    Set f = FSO.OpenTextFile(strLogFile, 8, True)
    f.WriteLine Now() & " [VBS] " & msg
    f.Close
    On Error GoTo 0
End Sub

' Run command hidden, wait for completion, return exit code
Function RunHidden(cmd)
    RunHidden = WshShell.Run(cmd, 0, True)
End Function

' Capture command output to temp file, return file path
Sub CaptureToTemp(cmd)
    RunHidden "cmd /c " & cmd & " > """ & strTempFile & """ 2>&1"
End Sub

' --- Main ---

WriteLog "=== Silent startup started ==="

' [1/5] Kill old processes
WriteLog "[1/5] Cleaning up old processes..."

' Kill via PID file
If FSO.FileExists(strPidFile) Then
    Set pidFile = FSO.OpenTextFile(strPidFile, 1)
    Do Until pidFile.AtEndOfStream
        pid = Trim(pidFile.ReadLine)
        If pid <> "" Then
            RunHidden "taskkill /F /T /PID " & pid
            WriteLog "  Killed PID " & pid
        End If
    Loop
    pidFile.Close
    FSO.DeleteFile strPidFile, True
End If

' Kill via port 8000 scan (fallback when PID file is missing)
RunHidden "cmd /c for /f ""tokens=5"" %a in ('netstat -aon ^| findstr "":8000.*LISTENING""') do taskkill /F /T /PID %a"

' Kill browser processes
RunHidden "taskkill /F /IM msedgewebview2.exe"
RunHidden "taskkill /F /IM msedge.exe"
WScript.Sleep 1000

' [2/5] Check .venv
WriteLog "[2/5] Checking dependencies..."
If Not FSO.FileExists(strVenv) Then
    WriteLog "[ERROR] .venv not found"
    WshShell.Popup ".venv not found!" & vbCrLf & _
                   "Run: python -m venv .venv" & vbCrLf & _
                   "Then: .venv\Scripts\pip install -r requirements.txt", _
                   10, "XianyuHunter Startup Failed", 16
    WScript.Quit 1
End If

' [3/5] Verify Python environment can import core modules
' Use WshShell.Run directly (no cmd /c) to avoid cmd's quote-stripping rules
WriteLog "[3/5] Verifying Python environment..."
exitCode = RunHidden("""" & strVenv & """ -c ""import xianyu_hunter; import uvicorn; import fastapi""")
If exitCode <> 0 Then
    WriteLog "[ERROR] Python dependencies missing (exit code " & exitCode & ")"
    WshShell.Popup "Python dependencies missing!" & vbCrLf & _
                   "Run: .venv\Scripts\pip install -r requirements.txt", _
                   10, "XianyuHunter Startup Failed", 16
    WScript.Quit 1
End If

' [4/5] Start Web server with scheduler (hidden, output to log)
' Wrap cmd /c argument in extra quotes to prevent cmd's quote-stripping
WriteLog "[4/5] Starting Web server with scheduler..."
WshShell.Run "cmd /c """"" & strVenv & """ -m xianyu_hunter web --with-scheduler > """ & strWebLog & """ 2>&1""", 0, False

' Wait for Web port to be ready (up to 40 seconds)
WriteLog "  Waiting for Web server..."
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
            WriteLog "  Web server ready (HTTP " & http.Status & ")"
            Exit For
        End If
    End If
    Err.Clear
    On Error GoTo 0
Next

If Not bWebReady Then
    WriteLog "[ERROR] Web server failed to start within 40 seconds"
    WshShell.Popup "Web server failed to start!" & vbCrLf & _
                   "Check logs\web.log for details.", _
                   10, "XianyuHunter Startup Failed", 16
    WScript.Quit 1
End If

' Record PID via port scan
CaptureToTemp "netstat -aon"
If FSO.FileExists(strTempFile) Then
    Set f = FSO.OpenTextFile(strTempFile, 1)
    Do Until f.AtEndOfStream
        line = f.ReadLine
        If InStr(line, ":8000") > 0 And InStr(line, "LISTENING") > 0 Then
            parts = Split(Trim(line))
            pid = parts(UBound(parts))
            Set pidFile = FSO.CreateTextFile(strPidFile, True)
            pidFile.Write pid
            pidFile.Close
            WriteLog "  Web server PID: " & pid
            Exit Do
        End If
    Loop
    f.Close
    FSO.DeleteFile strTempFile, True
End If

' [5/5] Verify process is alive
WriteLog "[5/5] Verifying service..."
bAlive = False
If FSO.FileExists(strPidFile) Then
    Set pidFile = FSO.OpenTextFile(strPidFile, 1)
    pid = Trim(pidFile.ReadLine)
    pidFile.Close
    If pid <> "" Then
        CaptureToTemp "tasklist /FI ""PID eq " & pid & """"
        If FSO.FileExists(strTempFile) Then
            Set f = FSO.OpenTextFile(strTempFile, 1)
            output = f.ReadAll
            f.Close
            FSO.DeleteFile strTempFile, True
            If InStr(output, pid) > 0 Then
                bAlive = True
                WriteLog "  [OK] Web server PID " & pid & " is running"
            End If
        End If
    End If
End If

If Not bAlive Then
    WriteLog "[ERROR] Web server process not running"
    WshShell.Popup "Web server process not running!" & vbCrLf & _
                   "Check logs\web.log for details.", _
                   10, "XianyuHunter Startup Failed", 16
    WScript.Quit 1
End If

' Open browser
WriteLog "Opening browser..."
WshShell.Run "http://127.0.0.1:8000/app/"

WriteLog "=== Silent startup completed ==="
WriteLog ""

Set FSO = Nothing
Set WshShell = Nothing
