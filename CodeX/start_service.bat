@echo off
cd /d C:\Brototype\CodeXLearning\Backend\CodeX

:: Activate virtual environment
call ..\venv\Scripts\activate

:: Start Daphne in a new window
start cmd /k "call ..\venv\Scripts\activate && daphne -b 0.0.0.0 -p 8000 CodeX.asgi:application"

:: Start Celery in a new window
start cmd /k "call ..\venv\Scripts\activate && celery -A CodeX worker --loglevel=info --pool=solo"

echo Both Celery and Daphne have been started in separate terminals.
pause
