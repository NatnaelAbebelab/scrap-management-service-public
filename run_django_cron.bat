@echo off
chcp 65001
cd /d "C:\Users\natna\Documents\Projects\JobProjects\SteelyRMIProjects\scrap-management-service-pull\scrap-management-service"
call "C:\Users\natna\Documents\Projects\JobProjects\SteelyRMIProjects\scrap-management-service-pull\scrap-management-service\venv\Scripts\activate.bat"
python -X utf8 manage.py runcrons >> cron_output.log 2>&1
