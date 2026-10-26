@echo off
chcp 65001 >nul
cd /d "%~dp0"
py -3 -m pip install -r requirements.txt
if not exist .env copy .env.example .env
echo.
echo 설치 완료. .env 파일을 메모장으로 열어 값을 채운 뒤 run.bat 을 실행하세요.
pause
