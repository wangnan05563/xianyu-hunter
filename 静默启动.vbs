' =============================================================
' Silent Startup (root launcher) - project root directory
' Double-click this file to launch the actual script in scripts/
' This file is a thin wrapper to keep the root directory clean
' =============================================================

Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

strDir = FSO.GetParentFolderName(WScript.ScriptFullName)
strScriptsDir = strDir & "\scripts"

' Verify scripts/ directory exists
If Not FSO.FolderExists(strScriptsDir) Then
    WshShell.Popup "scripts/ directory not found!" & vbCrLf & strScriptsDir, _
                   10, "XianyuHunter Startup Failed", 16
    WScript.Quit 1
End If

' Find the .vbs launcher in scripts/ by extension (avoids hardcoding
' the Chinese filename which breaks when file encoding is mismatched)
strLauncher = ""
For Each f In FSO.GetFolder(strScriptsDir).Files
    If LCase(FSO.GetExtensionName(f.Name)) = "vbs" Then
        strLauncher = f.Path
        Exit For
    End If
Next

If strLauncher = "" Then
    WshShell.Popup "Launcher script not found in scripts/" & vbCrLf & _
                   "Expected: a .vbs file in " & strScriptsDir, _
                   10, "XianyuHunter Startup Failed", 16
    WScript.Quit 1
End If

' Launch the actual script silently
WshShell.Run "wscript.exe """ & strLauncher & """", 0, False

Set FSO = Nothing
Set WshShell = Nothing
