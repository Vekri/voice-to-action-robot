@echo off
title Raja - LinkedIn video
cd /d "%~dp0"
echo.
echo  RAJA  -  LinkedIn demo
echo.
echo  1. Press any key to open Raja.
echo  2. When the window opens, press  Win + Alt + R  to record.
echo  3. The demo runs itself. Do not click.
echo  4. When it says DEMO COMPLETE, press  Win + Alt + R  again.
echo  5. Upload Videos\Captures and paste linkedin_post.txt
echo.
pause
python demo_linkedin.py
if errorlevel 1 pause
