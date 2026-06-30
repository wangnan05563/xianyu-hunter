# Pull CWE-tagged security issues and performance issues
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
Write-Host "STEP 1: CWE-tagged issues (security-related)"
Write-Host "=========================================="
$cweResp = Call-Api "20_cwe_issues" "$baseUrl/api/issues/search?componentKeys=$projectKey&tags=cwe&ps=100"
if ($cweResp) {
    Write-Host "Total CWE issues: $($cweResp.total)"
    $i = 0
    foreach ($iss in $cweResp.issues) {
        if ($i -lt 25) {
            Write-Host "  [$($iss.rule)] $($iss.severity) $($iss.component):$($iss.line)"
            Write-Host "    $($iss.message)"
            $i++
        }
    }
}

Write-Host ""
Write-Host "=========================================="
Write-Host "STEP 2: Performance-tagged issues"
Write-Host "=========================================="
$perfResp = Call-Api "21_performance_issues" "$baseUrl/api/issues/search?componentKeys=$projectKey&tags=performance&ps=100"
if ($perfResp) {
    Write-Host "Total performance issues: $($perfResp.total)"
    $i = 0
    foreach ($iss in $perfResp.issues) {
        if ($i -lt 15) {
            Write-Host "  [$($iss.rule)] $($iss.severity) $($iss.component):$($iss.line)"
            Write-Host "    $($iss.message)"
            $i++
        }
    }
}

Write-Host ""
Write-Host "=========================================="
Write-Host "STEP 3: Brain-overload tagged issues (top 20)"
Write-Host "=========================================="
$brainResp = Call-Api "22_brain_overload" "$baseUrl/api/issues/search?componentKeys=$projectKey&tags=brain-overload&ps=20"
if ($brainResp) {
    Write-Host "Total brain-overload: $($brainResp.total)"
    $i = 0
    foreach ($iss in $brainResp.issues) {
        if ($i -lt 15) {
            Write-Host "  [$($iss.rule)] $($iss.component):$($iss.line) - $($iss.message)"
            $i++
        }
    }
}

Write-Host ""
Write-Host "=========================================="
Write-Host "STEP 4: Get BUG type issues (reliability)"
Write-Host "=========================================="
$bugResp = Call-Api "23_bug_issues" "$baseUrl/api/issues/search?componentKeys=$projectKey&types=BUG&ps=100"
if ($bugResp) {
    Write-Host "Total bugs: $($bugResp.total)"
    $i = 0
    foreach ($iss in $bugResp.issues) {
        if ($i -lt 15) {
            Write-Host "  [$($iss.rule)] $($iss.severity) $($iss.component):$($iss.line)"
            Write-Host "    $($iss.message)"
            $i++
        }
    }
}

Write-Host ""
Write-Host "=========================================="
Write-Host "STEP 5: Try component/show with project key"
Write-Host "=========================================="
$showResp = Call-Api "24_project_show" "$baseUrl/api/components/show?component=$projectKey"

Write-Host ""
Write-Host "=========================================="
Write-Host "STEP 6: Get duplications stats (alternative endpoints)"
Write-Host "=========================================="

# Get all measures related to duplication
$dupeUrl = "$baseUrl/api/measures/component?component=$projectKey&metricKeys=duplicated_lines_density,duplicated_lines,duplicated_blocks,duplicated_files"
$dupeResp = Call-Api "25_duplication_measures" $dupeUrl
if ($dupeResp) {
    foreach ($m in $dupeResp.component.measures) {
        Write-Host "  $($m.metric): $($m.value)"
    }
}

Write-Host ""
Write-Host "=========================================="
Write-Host "STEP 7: Get top rules with high impact"
Write-Host "=========================================="
# Try facets on rules - to get a complete list of rules violated
$rulesFacetUrl = "$baseUrl/api/issues/search?componentKeys=$projectKey&facets=rules&ps=1"
$rulesFacetResp = Call-Api "26_rules_facet" $rulesFacetUrl
if ($rulesFacetResp -and $rulesFacetResp.facets) {
    foreach ($f in $rulesFacetResp.facets) {
        if ($f.property -eq "rules") {
            Write-Host "  All violated rules (count):"
            $i = 0
            foreach ($v in $f.values) {
                if ($i -lt 25) {
                    Write-Host "    $($v.val): $($v.count)"
                    $i++
                }
            }
        }
    }
}

Write-Host ""
Write-Host "=========================================="
Write-Host "DONE"
Write-Host "=========================================="
