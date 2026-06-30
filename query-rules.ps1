# Get details for BUG-type rules and additional rules
$ErrorActionPreference = "Continue"
$baseUrl = "http://localhost:9000"
$token = "sqa_fe4b774b40e19eca12e0f46a2f2f771f2d1a23bd"
$outDir = "d:\code\otherProjects\17_xianyu\sonar-results"
$headers = @{ Authorization = "Bearer $token" }

function Call-Api($name, $url) {
    try {
        $resp = Invoke-RestMethod -Uri $url -Headers $headers -Method Get
        $resp | ConvertTo-Json -Depth 20 | Out-File -FilePath "$outDir\$name.json" -Encoding utf8
        Write-Host "OK: $name"
        return $resp
    } catch {
        $status = ""
        if ($_.Exception.Response) { $status = $_.Exception.Response.StatusCode }
        Write-Host "FAIL ($status): $name - $($_.Exception.Message)"
        return $null
    }
}

# Get rule details for the most frequent BUG rules and BLOCKER rules
$rules = @(
    "typescript:S6757",      # this in functional components (BUG)
    "typescript:S3516",     # always returns same value (BLOCKER)
    "python:S3516",          # always returns same value (BLOCKER)
    "python:S1845",          # field name clash (BLOCKER)
    "typescript:S2871",      # missing compare function (CRITICAL BUG)
    "python:S7497",         # asyncio CancelledError handling
    "python:S7503",          # async related issue
    "python:S7487",          # async subprocess in async function
    "python:S7502",          # task garbage collection
    "typescript:S1082",     # keyboard listener
    "typescript:S1128",     # unused imports
    "typescript:S4325",     # type assertions
    "typescript:S6551",     # nullish vs or
    "typescript:S6582",     # unknown
    "typescript:S6848",     # unknown
    "typescript:S7773",     # unknown
    "python:S3457",         # unknown
    "python:S1066",         # unknown
    "python:S1481",         # unused local variables
    "typescript:S6582"      # unknown
)

foreach ($rule in $rules) {
    $ruleEnc = [System.Web.HttpUtility]::UrlEncode($rule)
    $resp = Call-Api "rule_$($rule -replace ':','_')" "$baseUrl/api/rules/show?key=$ruleEnc"
    if ($resp -and $resp.rule) {
        $r = $resp.rule
        $plainDesc = ""
        if ($r.htmlDesc) {
            $plainDesc = $r.htmlDesc -replace '<[^>]+>','' -replace '\s+',' '
            if ($plainDesc.Length -gt 250) { $plainDesc = $plainDesc.Substring(0, 250) + "..." }
        }
        Write-Host "[$rule]"
        Write-Host "  Name: $($r.name)"
        Write-Host "  Severity: $($r.severity) | Type: $($r.type) | Status: $($r.status)"
        Write-Host "  Tags: $($r.tags -join ', ')"
        if ($r.defaultDebtRemFn) {
            Write-Host "  Remediation: $($r.defaultDebtRemFn.baseEffort)"
        }
        Write-Host "  Desc: $plainDesc"
        Write-Host ""
    }
}

Write-Host ""
Write-Host "=========================================="
Write-Host "Get all facets counts (without filter)"
Write-Host "=========================================="
$allRulesFacet = Call-Api "30_all_rules_facet" "$baseUrl/api/issues/search?componentKeys=xianyu_hunter&facets=rules&ps=1"
if ($allRulesFacet -and $allRulesFacet.facets) {
    foreach ($f in $allRulesFacet.facets) {
        if ($f.property -eq "rules") {
            Write-Host "Total distinct rules violated: $($f.values.Count)"
            $i = 0
            foreach ($v in $f.values) {
                Write-Host "  $($v.val): $($v.count)"
                $i++
                if ($i -ge 50) { break }
            }
        }
    }
}
