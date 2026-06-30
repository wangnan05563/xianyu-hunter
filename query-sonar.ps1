# Query SonarQube REST API for project quality metrics
$ErrorActionPreference = "Continue"
$baseUrl = "http://localhost:9000"
$token = "sqa_fe4b774b40e19eca12e0f46a2f2f771f2d1a23bd"
$projectKey = "xianyu_hunter"
$headers = @{ Authorization = "Bearer $token" }
$outDir = "d:\code\otherProjects\17_xianyu\sonar-results"
New-Item -Path $outDir -ItemType Directory -Force | Out-Null

# Wait for task completion first
Write-Host "=== Checking task status ==="
$taskUrl = "$baseUrl/api/ce/task?id=126e3212-0853-4ecc-b02b-e50780c0dda1"
$taskResp = Invoke-RestMethod -Uri $taskUrl -Headers $headers -Method Get
$taskResp.task.status
$taskResp.task.analysisId

if ($taskResp.task.status -ne "SUCCESS") {
    Write-Host "Task not yet SUCCESS. Status: $($taskResp.task.status)"
    Write-Host "Waiting 10s and re-checking..."
    Start-Sleep -Seconds 10
    $taskResp = Invoke-RestMethod -Uri $taskUrl -Headers $headers -Method Get
    Write-Host "Re-checked status: $($taskResp.task.status)"
}

Write-Host ""
Write-Host "=== 1. Project measures ==="
$metricKeys = "ncloc,complexity,cognitive_complexity,violations,blocker_violations,critical_violations,major_violations,minor_violations,info_violations,bugs,vulnerabilities,code_smells,security_hotspots,coverage,tests,duplicated_lines_density,duplicated_lines,duplicated_blocks,duplicated_files,sqale_rating,security_rating,reliability_rating,sqale_index,sqale_debt_ratio,ncloc_language_distribution,directory_cycles,package_cycles,files,functions,classes,comment_lines_density,comment_lines"
$measureUrl = "$baseUrl/api/measures/component?component=$projectKey&metricKeys=$metricKeys"
try {
    $measures = Invoke-RestMethod -Uri $measureUrl -Headers $headers -Method Get
    $measures | ConvertTo-Json -Depth 10 | Out-File -FilePath "$outDir\01_measures.json" -Encoding utf8
    Write-Host "Saved measures to 01_measures.json"
    foreach ($m in $measures.component.measures) {
        Write-Host "  $($m.metric): $($m.value)$($m.period -replace '.*value=', ' (period value=' )$($m.period -replace '.*$', ')')"
    }
} catch {
    Write-Host "ERROR getting measures: $_"
}

Write-Host ""
Write-Host "=== 2. Quality gate status ==="
$qgUrl = "$baseUrl/api/qualitygates/project_status?projectKey=$projectKey"
try {
    $qg = Invoke-RestMethod -Uri $qgUrl -Headers $headers -Method Get
    $qg | ConvertTo-Json -Depth 10 | Out-File -FilePath "$outDir\02_quality_gate.json" -Encoding utf8
    Write-Host "Status: $($qg.projectStatus.status)"
    if ($qg.projectStatus.conditions) {
        foreach ($c in $qg.projectStatus.conditions) {
            Write-Host "  $($c.metricKey): actual=$($c.actualValue) status=$($c.status)"
        }
    }
} catch {
    Write-Host "ERROR getting quality gate: $_"
}

Write-Host ""
Write-Host "=== 3. Component tree (file-level breakdown) ==="
$treeUrl = "$baseUrl/api/components/tree?component=$projectKey&metricKeys=ncloc,complexity,violations,coverage,duplicated_lines_density&ps=500&strategy=leaves"
try {
    $tree = Invoke-RestMethod -Uri $treeUrl -Headers $headers -Method Get
    $tree | ConvertTo-Json -Depth 10 | Out-File -FilePath "$outDir\03_component_tree.json" -Encoding utf8
    Write-Host "Total components: $($tree.paging.total)"
    Write-Host "  Saved to 03_component_tree.json"
} catch {
    Write-Host "ERROR getting component tree: $_"
}

Write-Host ""
Write-Host "=== DONE Step 1-3 ==="
