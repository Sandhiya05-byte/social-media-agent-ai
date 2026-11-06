Set-Location D:\Social_media_Agent_AI\backend
$env:FFMPEG_BINARY = 'D:\ffmpeg\bin\ffmpeg.exe'
.\.venv\Scripts\python.exe -X utf8 -m pytest tests\test_research_agents.py tests\test_ollama_integration.py tests\test_content_approval_integration.py tests\test_phase5_integration.py -q -p no:cacheprovider *> pytest_fix.txt
