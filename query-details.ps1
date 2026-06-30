# Pull BLOCKER issues detail, top CRITICAL issues, rule details, hotspots alternative
$ErrorActionPreference = "Continue"
$baseUrl = "http://localhost:9000"
$token = "sqa_fe4b774b40e19eca12e0f46a2f2f771f2d1a23bd"
$projectKey = "xianyu_hunter"
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

Write-Host "=========================================="
Write-Host "STEP 1: Get BLOCKER issues detail"
Write-Host "=========================================="
$blockerResp = Call-Api "10_blocker_detail" "$baseUrl/api/issues/search?componentKeys=$projectKey&severities=BLOCKER&ps=50"
if ($blockerResp) {
    Write-Host "Total BLOCKER: $($blockerResp.total)"
    foreach ($iss in $blockerResp.issues) {
        Write-Host "  - [$($iss.rule)] $($iss.component):$($iss.line) | $($iss.message) | effort=$($iss.effort)"
    }
}

Write-Host ""
Write-Host "=========================================="
Write-Host "STEP 2: Top CRITICAL issues (first 30)"
Write-Host "=========================================="
$critResp = Call-Api "11_critical_top30" "$baseUrl/api/issues/search?componentKeys=$projectKey&severities=CRITICAL&ps=30"
if ($critResp) {
    Write-Host "Total CRITICAL: $($critResp.total)"
    $i = 0
    foreach ($iss in $critResp.issues) {
        if ($i -lt 15) {
            Write-Host "  - [$($iss.rule)] $($iss.component):$($iss.line) | $($iss.message)"
            $i++
        }
    }
}

Write-Host ""
Write-Host "=========================================="
Write-Host "STEP 3: Get top rule details"
Write-Host "=========================================="
$topRules = @(
    "python:S3776",
    "typescript:S3358",
    "typescript:S6757",
    "typescript:S6759",
    "typescript:S6479",
    "typescript:S7735",
    "python:S1192",
    "typescript:S1874",
    "typescript:S1854",
    "python:S125"
)
foreach ($rule in $topRules) {
    $ruleEnc = [System.Web.HttpUtility]::UrlEncode($rule)
    $resp = Call-Api "rule_$($rule -replace ':','_')" "$baseUrl/api/rules/show?key=$ruleEnc"
    if ($resp -and $resp.rule) {
        Write-Host "  [$rule] $($resp.rule.name)"
        Write-Host "    Severity: $($resp.rule.severity)"
        Write-Host "    Type: $($resp.rule.type)"
        if ($resp.rule.htmlDesc) {
            $plainText = $resp.rule.htmlDesc -replace '<[^>]+>','' -replace '\s+',' '
            if ($plainText.Length -gt 200) {
                $plainText = $plainText.Substring(0, 200) + "..."
            }
            Write-Host "    Desc: $plainText"
        }
    }
}

Write-Host ""
Write-Host "=========================================="
Write-Host "STEP 4: Try alternative security hotspot endpoints"
Write-Host "=========================================="

# Try multiple hotspot endpoint variants
$endpoints = @(
    @{ name="hotspots_search_v1"; url="$baseUrl/api/hotspots/search?projectKey=$projectKey&ps=500" },
    @{ name="hotspots_search_show_only"; url="$baseUrl/api/hotspots/search?projectKey=$projectKey&ps=10&status=TO_REVIEW" },
    @{ name="hotspots_search_status_all"; url="$baseUrl/api/hotspots/search?projectKey=$projectKey&ps=500&status=SAFE_TO_REVIEW,REVIEWED,TO_REVIEW" }
)
foreach ($ep in $endpoints) {
    $resp = Call-Api $ep.name $ep.url
    if ($resp -and $resp.hotspots) {
        Write-Host "  Found $($resp.hotspots.Count) hotspots (total: $($resp.paging.total))"
        break
    }
}

Write-Host ""
Write-Host "=========================================="
Write-Host "STEP 5: Try fetching duplications data via issues"
Write-Host "=========================================="

# Get all duplicated blocks count by querying the issues with duplications data
# Use /api/measures/component_tree for file-level duplication, but we know it's 403
# Try alternative: use /api/issues/search with rules filter for duplication rules
$dupeUrl = "$baseUrl/api/issues/search?componentKeys=$projectKey&tags=design&ps=20"
$dupeResp = Call-Api "14_duplication_issues" $dupeUrl
if ($dupeResp) {
    Write-Host "  Design tag issues: $($dupeResp.total)"
}

Write-Host ""
Write-Host "=========================================="
Write-Host "STEP 6: Get issue counts by file (top 20 files)"
Write-Host "=========================================="

$facetsUrl = "$baseUrl/api/issues/search?componentKeys=$projectKey&facets=files&ps=1"
$facetsResp = Call-Api "16_files_facet" $facetsUrl
if ($facetsResp -and $facetsResp.facets) {
    foreach ($f in $facetsResp.facets) {
        if ($f.property -eq "files") {
            $i = 0
            foreach ($v in $f.values) {
                if ($i -lt 20) {
                    Write-Host "  $($v.val): $($v.count)"
                    $i++
                }
            }
        }
    }
}

Write-Host ""
Write-Host "=========================================="
Write-Host "DONE - Step 4-6 complete"
Write-Host "=========================================="
