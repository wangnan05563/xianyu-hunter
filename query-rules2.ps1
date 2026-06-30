# Get rule details using [System.Uri]::EscapeDataString instead
$ErrorActionPreference = "Continue"
$baseUrl = "http://localhost:9000"
$token = "sqa_fe4b774b40e19eca12e0f46a2f2f771f2d1a23bd"
$outDir = "d:\code\otherProjects\17_xianyu\sonar-results"
$headers = @{ Authorization = "Bearer $token" }

function Call-Api($name, $url) {
    try {
        $resp = Invoke-RestMethod -Uri $url -Headers $headers -Method Get
        $resp | ConvertTo-Json -Depth 20 | Out-File -FilePath "$outDir\$name.json" -Encoding utf8
        return $resp
    } catch {
        return $null
    }
}

# Use Add-Type then Uri method
Add-Type -AssemblyName System.Web | Out-Null

# Get rule details for remaining important rules
$rules = @(
    "python:S3516",
    "python:S1845",
    "typescript:S3516",
    "typescript:S2871",
    "python:S7497",
    "python:S7503",
    "python:S7487",
    "python:S7502",
    "typescript:S1082",
    "typescript:S1128",
    "typescript:S4325",
    "typescript:S6551",
    "typescript:S6582",
    "typescript:S6848",
    "typescript:S7773",
    "python:S3457",
    "python:S1066",
    "python:S1481",
    "python:S5713",
    "python:S1172",
    "python:S5890",
    "python:S7483",
    "python:S1871",
    "python:S6353",
    "python:S7504",
    "python:S5850",
    "python:S2737",
    "python:S6903",
    "python:S107",
    "typescript:S2486",
    "typescript:S6772",
    "typescript:S7781",
    "typescript:S6853",
    "typescript:S6844",
    "typescript:S7784",
    "typescript:S7748",
    "typescript:S4624",
    "typescript:S7770",
    "typescript:S2310",
    "typescript:S2004",
    "typescript:S3696",
    "typescript:S7747",
    "typescript:S7781"
)

$ruleDetails = @()
foreach ($rule in $rules) {
    # Just URL-encode the colon
    $ruleEnc = $rule -replace ':','%3A'
    $url = "$baseUrl/api/rules/show?key=$ruleEnc"
    $resp = Call-Api "rule_$($rule -replace ':','_')" $url
    if ($resp -and $resp.rule) {
        $r = $resp.rule
        $plainDesc = ""
        if ($r.htmlDesc) {
            $plainDesc = $r.htmlDesc -replace '<[^>]+>','' -replace '\s+',' '
            if ($plainDesc.Length -gt 300) { $plainDesc = $plainDesc.Substring(0, 300) + "..." }
        }
        $remediation = ""
        if ($r.defaultDebtRemFn) { $remediation = $r.defaultDebtRemFn.baseEffort }
        $obj = [PSCustomObject]@{
            rule = $rule
            name = $r.name
            severity = $r.severity
            type = $r.type
            tags = ($r.tags -join ',')
            remediation = $remediation
            description = $plainDesc
        }
        $ruleDetails += $obj
        Write-Host "[$rule] $($r.severity) $($r.type) - $($r.name)"
    }
}

Write-Host ""
Write-Host "Total rules detailed: $($ruleDetails.Count)"
$ruleDetails | ConvertTo-Csv -NoTypeInformation | Out-File -FilePath "$outDir\40_rules_summary.csv" -Encoding utf8
Write-Host "Saved rules summary CSV"
