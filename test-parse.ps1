$errors = $null
$tokens = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile('d:\code\otherProjects\17_xianyu\.trae\skills\xianyu-sonarqube-mcp\scripts\verify-connection.ps1', [ref]$tokens, [ref]$errors)
if ($errors) {
    Write-Host "Found $($errors.Count) parse errors:"
    $errors | ForEach-Object {
        Write-Host ("Line {0}:{1} - {2}" -f $_.Extent.StartLineNumber, $_.Extent.StartColumnNumber, $_.Message)
    }
} else {
    Write-Host "No parse errors"
}
