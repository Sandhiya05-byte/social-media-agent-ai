$body = @{
    campaign_topic = 'Home coffee brewing for beginners'
    target_audience = 'coffee beginners'
    platforms = @('Instagram')
    campaign_objective = 'Teach pour-over basics.'
    content_type = 'short-form'
} | ConvertTo-Json

try {
    $r = Invoke-RestMethod `
        -Uri 'http://127.0.0.1:8001/api/orchestration/workflows' `
        -Method Post `
        -Body ([Text.Encoding]::UTF8.GetBytes($body)) `
        -ContentType 'application/json' `
        -TimeoutSec 600

    $r | ConvertTo-Json -Depth 20 |
        Set-Content 'D:\Social_media_Agent_AI\backend\coffee_workflow_result.json'

    'WORKFLOW COMPLETED'
    "ID: $($r.workflow_id)"
    "STATUS: $($r.status)"
}
catch {
    "WORKFLOW FAILED: $($_.Exception.Message)" |
        Set-Content 'D:\Social_media_Agent_AI\backend\coffee_workflow_error.txt'
}
