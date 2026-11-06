Set-Location D:\Social_media_Agent_AI\backend
$env:FFMPEG_BINARY = 'D:\ffmpeg\bin\ffmpeg.exe'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8765 *> uvicorn_live.log
