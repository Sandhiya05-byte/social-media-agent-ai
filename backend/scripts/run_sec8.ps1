Set-Location D:\Social_media_Agent_AI\backend
$env:FFMPEG_BINARY = 'D:\ffmpeg\bin\ffmpeg.exe'
.\.venv\Scripts\python.exe -X utf8 -m pytest tests\test_phase5_integration.py tests\test_content_approval_integration.py tests\test_phase4_content_workflow.py -q -p no:cacheprovider *> pytest_sec8.txt
