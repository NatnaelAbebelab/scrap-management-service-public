@echo off
chcp 65001
cd /d "C:\inetpub\wwwroot\scrap-management-service"
call "C:\inetpub\wwwroot\scrap-management-service\venv\Scripts\activate.bat"
python -X utf8 manage.py runcrons >> cron_output.log 2>&1
