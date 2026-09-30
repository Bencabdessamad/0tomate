@echo off
REM Lancement quotidien de la veille (Planificateur de tâches Windows).
REM Adapter le chemin du dossier et, si besoin, celui de python.exe.
cd /d "%~dp0"
REM set ANTHROPIC_API_KEY=sk-ant-...   (préférer une variable d'environnement utilisateur)
python veille.py --heures 24 --sortie excel >> sorties\planifie.log 2>&1
