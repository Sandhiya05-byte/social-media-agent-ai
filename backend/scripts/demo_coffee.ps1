$ErrorActionPreference = 'Stop'
$base = 'http://127.0.0.1:8001'

function Post($path, $body) {
    $json = $body | ConvertTo-Json -Depth 6
    return Invoke-RestMethod -Uri "$base$path" -Method Post -Body ([System.Text.Encoding]::UTF8.GetBytes($json)) -ContentType 'application/json; charset=utf-8' -TimeoutSec 400
}
function GetReq($path) { return Invoke-RestMethod -Uri "$base$path" -TimeoutSec 30 }

$body = @{
    campaign_topic = 'Home coffee brewing for beginners'
    target_audience = 'coffee beginners'
    platforms = @('Instagram')
    campaign_objective = 'Teach pour-over basics.'
    content_type = 'short-form'
}
$r = Post '/api/orchestration/workflows' $body
$c = $r.context
Write-Output ("wf={0} status={1}" -f $r.workflow_id, $r.status)
Write-Output ("providers: {0}" -f ($c.research_findings.provider_statuses | ConvertTo-Json -Compress))
Write-Output ("sources: {0}" -f $c.research_findings.source_references.Count)
Write-Output ("title: {0}" -f $c.creative_output.title)
Write-Output ("gen_source: {0}" -f $c.creative_output.generation_source)
Write-Output ("video: {0} dur={1}s audio={2}" -f $c.video_output.video_url, $c.video_output.duration_seconds, $c.video_output.audio_enabled)

$q = GetReq '/api/content'
$item = $q | Where-Object { $_.workflow_id -eq $r.workflow_id } | Select-Object -First 1
Write-Output ("auto-bridged content item #{0} [{1}]: {2}" -f $item.id, $item.status, $item.title)

# Verify the MP4 is served
$h = Invoke-WebRequest -Uri "$base$($c.video_output.video_url)" -Method Head -TimeoutSec 20
Write-Output ("MP4 HTTP {0}, {1} bytes" -f $h.StatusCode, $h.Headers.'Content-Length')
