$ErrorActionPreference = 'Stop'
$base = 'http://127.0.0.1:8001'

function Post($path, $body) {
    $json = $body | ConvertTo-Json -Depth 6
    return Invoke-RestMethod -Uri "$base$path" -Method Post -Body ([System.Text.Encoding]::UTF8.GetBytes($json)) -ContentType 'application/json; charset=utf-8'
}
function GetReq($path) { return Invoke-RestMethod -Uri "$base$path" -TimeoutSec 30 }

foreach ($camp in @(
    @{ topic = 'AI tools for college students'; audience = 'College students'; objective = 'Educate students about useful AI tools.' },
    @{ topic = 'Sustainable fashion for Gen Z'; audience = 'Young adults'; objective = 'Show affordable sustainable fashion choices.' }
)) {
    Write-Output "########## CAMPAIGN: $($camp.topic) ##########"
    $wf = Post '/api/orchestration/workflows' @{
        campaign_topic = $camp.topic
        target_audience = $camp.audience
        platforms = @('Instagram', 'YouTube')
        campaign_objective = $camp.objective
        content_type = 'short-form'
    }
    $wid = $wf.workflow_id
    $ctx = $wf.context
    Write-Output ("workflow_id={0} status={1}" -f $wid, $wf.status)

    $research = $ctx.research_findings
    Write-Output ("research providers: {0} | sources: {1}" -f ($research.provider_statuses | ConvertTo-Json -Compress), $research.source_references.Count)
    Write-Output ("first source: {0}" -f $research.source_references[0].title)

    $comp = $ctx.competitor_findings
    Write-Output ("competitor obs: {0} | first: {1}" -f $comp.observations.Count, $comp.observations[0].summary.Substring(0, [Math]::Min(90, $comp.observations[0].summary.Length)))

    Write-Output ("recommended hook: {0}" -f $ctx.recommended_hook)
    $creative = $ctx.creative_output
    Write-Output ("title: {0}" -f $creative.title)
    Write-Output ("generation_source: {0}" -f $creative.generation_source)
    Write-Output ("script words: {0}" -f $creative.script.Split(' ').Count)

    $video = $ctx.video_output
    Write-Output ("video_url: {0} | duration: {1}s | audio: {2} | engine: {3}" -f $video.video_url, $video.duration_seconds, $video.audio_enabled, $video.render_engine)

    # MP4 served?
    if ($video.video_url) {
        $h = Invoke-WebRequest -Uri "$base$($video.video_url)" -Method Head -TimeoutSec 20
        Write-Output ("MP4 HTTP {0}, {1} bytes, {2}" -f $h.StatusCode, $h.Headers.'Content-Length', $h.Headers.'Content-Type')
    }

    # Auto-created ContentItem
    $queue = GetReq '/api/content'
    $item = $queue | Where-Object { $_.workflow_id -eq $wid } | Select-Object -First 1
    Write-Output ("auto-created content item #{0} [{1}]: {2}" -f $item.id, $item.status, $item.title)

    # Unapproved scheduling must fail
    try {
        Post "/api/content/$($item.id)/schedule" @{ scheduled_for = '2031-03-01T10:00:00Z' } | Out-Null
        Write-Output 'ERROR: schedule succeeded before approval!'
    } catch {
        Write-Output ("pre-approval schedule refused: HTTP {0}" -f $_.Exception.Response.StatusCode.value__)
    }

    # Approve + schedule
    $app = Post "/api/content/$($item.id)/approve" @{ approved_by = 'creator'; notes = 'demo approval' }
    Write-Output ("approved: status={0} by={1}" -f $app.status, $app.approved_by)
    $sched = Post "/api/content/$($item.id)/schedule" @{ scheduled_for = '2031-03-01T10:00:00Z' }
    Write-Output ("scheduled: status={0} for={1}" -f $sched.status, $sched.scheduled_for)
    Write-Output ""
}

Write-Output "########## DASHBOARD (real data) ##########"
$stats = GetReq '/api/dashboard/stats'
Write-Output ("content total={0} by_status={1}" -f $stats.content.total, ($stats.content.by_status | ConvertTo-Json -Compress))
Write-Output ("workflows total={0} by_status={1}" -f $stats.workflows.total, ($stats.workflows.by_status | ConvertTo-Json -Compress))
Write-Output ("agent_executions: total={0} completed={1} failed={2}" -f $stats.agent_executions.total, $stats.agent_executions.completed, $stats.agent_executions.failed)
