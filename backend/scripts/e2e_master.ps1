$ErrorActionPreference = 'Stop'
$base = 'http://127.0.0.1:8001'

function Post($path, $body) {
    $json = $body | ConvertTo-Json -Depth 6
    return Invoke-RestMethod -Uri "$base$path" -Method Post -Body ([System.Text.Encoding]::UTF8.GetBytes($json)) -ContentType 'application/json; charset=utf-8' -TimeoutSec 500
}
function GetReq($path) { return Invoke-RestMethod -Uri "$base$path" -TimeoutSec 30 }

Write-Output "=== SEVEN-AGENT LIVE E2E: Home coffee brewing ==="
$r = Post '/api/orchestration/workflows' @{
    campaign_topic = 'Home coffee brewing for beginners'
    target_audience = 'Coffee beginners'
    platforms = @('Instagram')
    campaign_objective = 'Teach beginners pour-over coffee basics.'
    content_type = 'short-form'
}
$wid = $r.workflow_id
$c = $r.context
Write-Output ("workflow_id={0} status={1}" -f $wid, $r.status)

$rf = $c.research_findings
Write-Output ("[A1 Trend] providers={0} sources={1}" -f ($rf.provider_statuses | ConvertTo-Json -Compress), $rf.source_references.Count)
Write-Output ("[A1] first source: {0}" -f $rf.source_references[0].title)

$cf = $c.competitor_findings
Write-Output ("[A2 Competitor] obs={0} urls={1}" -f $cf.observations.Count, ($cf.competitor_urls | Select-Object -First 2))

Write-Output ("[A4 Hooks] recommended: {0}" -f $c.recommended_hook)

$co = $c.creative_output
Write-Output ("[A5 Creative] gen_source={0}" -f $co.generation_source)
Write-Output ("[A5] title: {0}" -f $co.title)
Write-Output ("[A5] script words: {0}" -f $co.script.Split(' ').Count)

$vo = $c.video_output
Write-Output ("[A6 Video] url={0} dur={1}s audio={2} engine={3} scenes={4}" -f $vo.video_url, $vo.duration_seconds, $vo.audio_enabled, $vo.render_engine, $vo.scene_count)
$h = Invoke-WebRequest -Uri "$base$($vo.video_url)" -Method Head -TimeoutSec 20
Write-Output ("[A6] MP4 served: HTTP {0}, {1} bytes" -f $h.StatusCode, $h.Headers.'Content-Length')

$q = GetReq '/api/content'
$item = $q | Where-Object { $_.workflow_id -eq $wid } | Select-Object -First 1
Write-Output ("[Bridge] content item #{0} [{1}]: {2}" -f $item.id, $item.status, $item.title)

# Approval gate
try {
    Post "/api/content/$($item.id)/schedule" @{ scheduled_for = '2031-05-01T09:00:00Z' } | Out-Null
    Write-Output '[GATE] FAIL: scheduled without approval!'
} catch {
    Write-Output ("[GATE] correctly refused pre-approval schedule: HTTP {0}" -f $_.Exception.Response.StatusCode.value__)
}

$app = Post "/api/content/$($item.id)/approve" @{ approved_by = 'creator'; notes = 'live e2e approval' }
Write-Output ("[Approval] status={0} by={1}" -f $app.status, $app.approved_by)

$sched = Post "/api/content/$($item.id)/schedule" @{ scheduled_for = '2031-05-01T09:00:00Z' }
Write-Output ("[Scheduling] status={0} for={1}" -f $sched.status, $sched.scheduled_for)

$stats = GetReq '/api/dashboard/stats'
Write-Output ("[Dashboard] content={0} workflows={1} agent_execs={2}" -f $stats.content.total, $stats.workflows.total, $stats.agent_executions.total)
Write-Output "=== E2E COMPLETE ==="
