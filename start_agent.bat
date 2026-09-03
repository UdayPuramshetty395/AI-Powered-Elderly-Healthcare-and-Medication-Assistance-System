@echo off
echo =====================================
echo  ElderCare Voice Reminder Agent
echo  Telugu voice plays automatically
echo  Keep this window open
echo =====================================
call venv\Scripts\activate
python reminder_agent.py --poll --repeat-minutes 2
pause
