# Comprehensive SonarQube REST API query
$ErrorActionPreference = "Continue"
$baseUrl = "http://localhost:9000"
$token = "sqa_fe4b774b40e19eca12e0f46a2f2f771f2d1a23bd"
$projectKey = "xianyu_hunter"
$outDir = "d:\code\otherProjects\17_xianyu\sonar-results"
New-Item -Path $outDir -ItemType Directory -Force | Out-Null
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
Write-Host "STEP 1: Project measures (batched)"
Write-Host "=========================================="

# Test which metric names are valid by querying in smaller batches
$batches = @(
    "ncloc,ncloc_language_distribution,files,functions,classes,directories,comment_lines,comment_lines_density",
    "complexity,cognitive_complexity",
    "violations,blocker_violations,critical_violations,major_violations,minor_violations,info_violations",
    "bugs,vulnerabilities,code_smells,security_hotspots,security_hotspots_reviewed,security_review_rating",
    "coverage,tests,duplicated_lines_density,duplicated_lines,duplicated_blocks,duplicated_files",
    "sqale_rating,security_rating,reliability_rating,sqale_index,sqale_debt_ratio"
)

$allMeasures = @()
foreach ($batch in $batches) {
    $url = "$baseUrl/api/measures/component?component=$projectKey&metricKeys=$batch"
    $resp = Call-Api "measures_batch_$($batch.Split(',')[0])" $url
    if ($resp -and $resp.component.measures) {
        foreach ($m in $resp.component.measures) {
            $allMeasures += $m
            Write-Host "  $($m.metric): $($m.value)"
        }
    }
}

# Combine measures into single file
$combined = @{ component = "xianyu_hunter"; measures = $allMeasures }
$combined | ConvertTo-Json -Depth 5 | Out-File -FilePath "$outDir\01_measures_all.json" -Encoding utf8
Write-Host "Total measures collected: $($allMeasures.Count)"

Write-Host ""
Write-Host "=========================================="
Write-Host "STEP 2: Issues by severity"
Write-Host "=========================================="

# Get counts by severity - first query total to understand distribution
$severities = @("BLOCKER", "CRITICAL", "MAJOR", "MINOR", "INFO")
foreach ($sev in $severities) {
    # First page to get total
    $url = "$baseUrl/api/issues/search?componentKeys=$projectKey&severities=$sev&ps=500"
    $resp = Call-Api "issues_$sev" $url
    if ($resp) {
        Write-Host "  $sev : total=$($resp.total), effort=$($resp.effortTotal)min"
    }
}

Write-Host ""
Write-Host "=========================================="
Write-Host "STEP 3: Issues by software quality impact"
Write-Host "=========================================="

$qualities = @("SECURITY", "RELIABILITY", "MAINTAINABILITY")
foreach ($q in $qualities) {
    $url = "$baseUrl/api/issues/search?componentKeys=$projectKey&impactSoftwareQualities=$q&ps=500"
    $resp = Call-Api "issues_quality_$q" $url
    if ($resp) {
        Write-Host "  $q : total=$($resp.total), effort=$($resp.effortTotal)min"
    }
}

Write-Host ""
Write-Host "=========================================="
Write-Host "STEP 4: Issues by type"
Write-Host "=========================================="

$types = @("BUG", "VULNERABILITY", "CODE_SMELL")
foreach ($t in $types) {
    $url = "$baseUrl/api/issues/search?componentKeys=$projectKey&types=$t&ps=500"
    $resp = Call-Api "issues_type_$t" $url
    if ($resp) {
        Write-Host "  $t : total=$($resp.total), effort=$($resp.effortTotal)min"
    }
}

Write-Host ""
Write-Host "=========================================="
Write-Host "STEP 5: Security hotspots"
Write-Host "=========================================="

$hotspotsUrl = "$baseUrl/api/hotspots/search?projectKey=$projectKey&ps=500"
$hotspots = Call-Api "05_hotspots" $hotspotsUrl
if ($hotspots) {
    Write-Host "  Total hotspots: $($hotspots.paging.total)"
}

Write-Host ""
Write-Host "=========================================="
Write-Host "STEP 6: Top files by issue count"
Write-Host "=========================================="

# Use facets to get component distribution
$facetsUrl = "$baseUrl/api/issues/search?componentKeys=$projectKey&facets=files,severities,impactSoftwareQualities,rules,types,tags&ps=1"
$facets = Call-Api "06_facets" $facetsUrl
if ($facets -and $facets.facets) {
    foreach ($f in $facets.facets) {
        Write-Host "  Facet: $($f.property)"
        $i = 0
        foreach ($v in $f.values) {
            if ($i -lt 10) {
                Write-Host "    $($v.val): $($v.count)"
                $i++
            }
        }
    }
}

Write-Host ""
Write-Host "=========================================="
Write-Host "STEP 7: Quality gate status"
Write-Host "=========================================="

$qgUrl = "$baseUrl/api/qualitygates/project_status?projectKey=$projectKey"
$qg = Call-Api "07_quality_gate" $qgUrl
if ($qg) {
    Write-Host "  Overall status: $($qg.projectStatus.status)"
    if ($qg.projectStatus.conditions) {
        foreach ($c in $qg.projectStatus.conditions) {
            Write-Host "    $($c.metricKey): actual=$($c.actualValue) status=$($c.status)"
        }
    }
}

Write-Host ""
Write-Host "=========================================="
Write-Host "DONE - All data saved to $outDir"
Write-Host "=========================================="
