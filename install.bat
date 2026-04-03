@echo off
echo ============================================
echo   Wind Farm Project - Setup
echo ============================================
echo.
echo This will install everything you need.
echo It may take a few minutes. Please wait...
echo.

conda create -n floris_env python=3.10 -y
if errorlevel 1 (
    echo.
    echo ERROR: conda not found. Please install Anaconda first:
    echo https://www.anaconda.com/download
    pause
    exit /b 1
)

call conda activate floris_env

pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERROR: Something went wrong during installation.
    echo Make sure you are connected to the internet and try again.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Setup complete! You are ready to go.
echo ============================================
echo.
echo To run the project, open a terminal and follow
echo the instructions in README.md.
echo.
pause
