Set-Location D:\Social_media_Agent_AI\backend
$env:FFMPEG_BINARY = 'D:\ffmpeg\bin\ffmpeg.exe'
.\.venv\Scripts\python.exe -X utf8 -m pytest tests -q -p no:cacheprovider *> pytest_master.txt
