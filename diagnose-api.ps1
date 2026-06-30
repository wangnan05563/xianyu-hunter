# Diagnose API endpoint availability
$ErrorActionPreference = "Continue"
$baseUrl = "http://localhost:9000"
$token = "sqa_fe4b774b40e19eca12e0f46a2f2f771f2d1a23bd"
$projectKey = "xianyu_hunter"
$outDir = "d:\code\otherProjects\17_xianyu\sonar-results"
New-Item -Path $outDir -ItemType Directory -Force | Out-Null

# Use Basic auth with empty username + token as password (some endpoints prefer this)
$basicAuth = "Basic " + [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes(":$token"))
$headersBasic = @{ Authorization = $basicAuth }
$headersBearer = @{ Authorization = "Bearer $token" }
$headers = $headersBearer

function Try-Endpoint($name, $url, $headersSet) {
    Write-Host ""
    Write-Host "=== $name ==="
    Write-Host "URL: $url"
    try {
        $resp = Invoke-RestMethod -Uri $url -Headers $headersSet -Method Get
        $resp | ConvertTo-Json -Depth 10 | Out-File -FilePath "$outDir\$name.json" -Encoding utf8
        Write-Host "OK - saved to $name.json"
        return $resp
    } catch {
        $status = $_.Exception.Response.StatusCode
        Write-Host "FAILED ($status): $($_.Exception.Message)"
        try {
            $stream = $_.Exception.Response.GetResponseStream()
            $reader = New-Object System.IO.StreamReader($stream)
            $body = $reader.ReadToEnd()
            Write-Host "Response body: $body"
            $body | Out-File -FilePath "$outDir\${name}_error.txt" -Encoding utf8
        } catch {}
        return $null
    }
}

# Try with single metric first to debug
Try-Endpoint "test_measures_single" "$baseUrl/api/measures/component?component=$projectKey&metricKeys=ncloc" $headersBearer

# Try alternative measure endpoint
Try-Endpoint "test_measures_component_tree" "$baseUrl/api/measures/component_tree?component=$projectKey&metricKeys=ncloc&ps=5" $headersBearer

# Try with basic auth
Try-Endpoint "test_measures_basic" "$baseUrl/api/measures/component?component=$projectKey&metricKeys=ncloc" $headersBasic

# Try /api/components/show to verify project exists
Try-Endpoint "test_components_show" "$baseUrl/api/components/show?component=$projectKey" $headersBearer

# Try /api/components/tree with component query
Try-Endpoint "test_components_tree_basic" "$baseUrl/api/components/tree?component=$projectKey&ps=5" $headersBearer

# Try issue search (basic, should work)
Try-Endpoint "test_issues_basic" "$baseUrl/api/issues/search?componentKeys=$projectKey&ps=5" $headersBearer

# Try /api/measures/component with project-specific path
Try-Endpoint "test_measures_v2" "$baseUrl/api/v2/measures/component?component=$projectKey&metricKeys=ncloc" $headersBearer

Write-Host ""
Write-Host "=== Diagnosis complete ==="
