$tokens = [System.Management.Automation.PSParser]::Tokenize((Get-Content 'D:\Social_media_Agent_AI\start_system.ps1' -Raw), [ref]$null)
Write-Output ("syntax OK, {0} tokens" -f $tokens.Count)
