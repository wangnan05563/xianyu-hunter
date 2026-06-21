$env:WEB_TOKEN = (Select-String -Path "d:\code\otherProjects\17_xianyu\.env" -Pattern "^WEB_TOKEN=").Line.Split("=",2)[1].Trim()
Start-Sleep -Seconds 3
$r = curl.exe -s -H "Authorization: Bearer $env:WEB_TOKEN" "http://127.0.0.1:8000/api/evaluations?limit=4"
[System.IO.File]::WriteAllText("d:\code\otherProjects\17_xianyu\eval_resp.json", $r)
$j = $r | ConvertFrom-Json
"count: $($j.count), total: $($j.total)"
foreach ($i in $j.items) {
    "---"
    "title: $($i.payload.item_title)"
    "seller_nick: [$($i.payload.seller_nick)]"
    "region: [$($i.payload.region)]"
    "publish_time_text: [$($i.payload.publish_time_text)]"
    "seller_credit: [$($i.payload.seller_credit)]"
    "condition_label: [$($i.condition_label)]"
    "condition_label_override: [$($i.payload.condition_label_override)]"
}
