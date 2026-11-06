$ErrorActionPreference = 'Stop'
$base = 'http://127.0.0.1:8765'

function Post($path, $body) {
    $json = $body | ConvertTo-Json -Depth 6
    return Invoke-RestMethod -Uri "$base$path" -Method Post -Body ([System.Text.Encoding]::UTF8.GetBytes($json)) -ContentType 'application/json; charset=utf-8'
}
function GetReq($path) { return Invoke-RestMethod -Uri "$base$path" -TimeoutSec 30 }

Write-Output "=== 1. Run full 7-agent workflow ==="
$wf = Post '/api/orchestration/workflows' @{
    campaign_topic = 'Local AI video automation'
    target_audience = 'solo creators'
    platforms = @('Instagram')
    campaign_objective = 'Teach creators to automate video production offline.'
    content_type = 'short-form'
    competitor_urls = @('https://example.com/competitor')
    rss_sources = @('https://example.com/rss')
    creator_writing_samples = @('Clarity compounds. Systems are scalable.')
}
$wid = $wf.workflow_id
Write-Output ("workflow_id = {0}, status = {1}" -f $wid, $wf.status)
Write-Output ("video_url = {0}" -f $wf.context.video_output.video_url)
Write-Output ("duration_seconds = {0}, audio_enabled = {1}, render_engine = {2}" -f $wf.context.video_output.duration_seconds, $wf.context.video_output.audio_enabled, $wf.context.video_output.render_engine)
Write-Output ("script_sufficient = {0}" -f $wf.context.video_output.script_sufficient)

Write-Output "=== 2. Verify generated MP4 is served ==="
$videoUrl = $wf.context.video_output.video_url
$resp = Invoke-WebRequest -Uri "$base$videoUrl" -Method Head -TimeoutSec 30
Write-Output ("{0} -> HTTP {1}, {2}, content-type {3}" -f $videoUrl, $resp.StatusCode, $resp.Headers.'Content-Length', $resp.Headers.'Content-Type')

Write-Output "=== 3. Bridge workflow content into Content Studio approval queue ==="
$item = Post "/api/content/from-workflow/$wid" @{}
Write-Output ("content_id = {0}, status = {1}" -f $item.id, $item.status)
Write-Output ("media_url = {0}" -f $item.media_url)
Write-Output ("validation_errors = {0}" -f ($item.validation_errors -join '; '))

Write-Output "=== 4. Schedule before approval must fail ==="
try {
    Post "/api/content/$($item.id)/schedule" @{ scheduled_for = '2030-01-01T10:00:00Z' } | Out-Null
    Write-Output 'ERROR: scheduling succeeded without approval!'
} catch {
    Write-Output ("Correctly refused: HTTP {0}" -f $_.Exception.Response.StatusCode.value__)
}

Write-Output "=== 5. Approve the content item ==="
$approved = Post "/api/content/$($item.id)/approve" @{ approved_by = 'creator'; notes = 'Manual review passed.' }
Write-Output ("status = {0}, approved_by = {1}, approved_at = {2}" -f $approved.status, $approved.approved_by, $approved.approved_at)

Write-Output "=== 6. Schedule the approved content ==="
$sched = Post "/api/content/$($item.id)/schedule" @{ scheduled_for = '2030-01-02T15:00:00Z' }
Write-Output ("status = {0}, scheduled_for = {1}" -f $sched.status, $sched.scheduled_for)

Write-Output "=== 7. Verify queue and calendar state ==="
$queue = GetReq '/api/content'
Write-Output ("queue size = {0}" -f $queue.Count)
$queue | ForEach-Object { Write-Output ("  #{0} [{1}] {2}" -f $_.id, $_.status, $_.title) }

Write-Output "=== 8. Approval flow complete ==="
