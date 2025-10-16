@echo off
title Glitch Create Browser - Installer
color 0A
echo ========================================
echo    Glitch Create Browser Installer
echo ========================================
echo.

:CHECK_PYTHON
echo Checking for Python installation...
python --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Python is installed!
    python --version
    echo.
    goto ASK_INSTALL_DEPS
) else (
    echo [!] Python is not detected in PATH
    echo.
    goto ASK_INSTALL_PYTHON
)

:ASK_INSTALL_PYTHON
set /p pythoninstalled="Did you install Python? (y/n): "
if /i "%pythoninstalled%"=="y" goto PYTHON_PATH_ISSUE
if /i "%pythoninstalled%"=="n" goto INSTALL_PYTHON
echo Invalid input. Please enter 'y' or 'n'.
goto ASK_INSTALL_PYTHON

:PYTHON_PATH_ISSUE
echo.
echo Python might be installed but not added to PATH.
echo Please make sure Python is in your system PATH and try again.
echo.
echo Tip: When installing Python, check "Add Python to PATH"
echo.
pause
exit

:INSTALL_PYTHON
echo.
echo ========================================
echo    Installing Python
echo ========================================
echo.
echo Opening Python download page...
echo Please download and install Python 3.8 or higher
echo IMPORTANT: Check "Add Python to PATH" during installation!
echo.
echo After installing Python, restart this installer.
echo.
start https://www.python.org/downloads/
pause
exit

:ASK_INSTALL_DEPS
echo.
set /p installdeps="Do you want to install required dependencies? (y/n): "
if /i "%installdeps%"=="y" goto INSTALL_DEPS
if /i "%installdeps%"=="n" goto DOWNLOAD_FILE
echo Invalid input. Please enter 'y' or 'n'.
goto ASK_INSTALL_DEPS

:INSTALL_DEPS
echo.
echo ========================================
echo    Installing Dependencies
echo ========================================
echo.
echo Installing required Python packages...
echo This may take a few minutes...
echo.

pip install --upgrade pip
echo.
echo Installing PyQt6...
pip install PyQt6
echo.
echo Installing PyQt6-WebEngine...
pip install PyQt6-WebEngine
echo.
echo Installing requests...
pip install requests
echo.

if %errorlevel% equ 0 (
    echo.
    echo [OK] All dependencies installed successfully!
    echo.
) else (
    echo.
    echo [!] Some dependencies failed to install.
    echo Please check the errors above and try again.
    echo.
    pause
    exit
)

:DOWNLOAD_FILE
echo.
echo ========================================
echo    Downloading Browser File
echo ========================================
echo.
echo Opening download link in your browser...
start https://github.com/Epic8782729/Create-Browser/releases/download/browser/create_browser.py
echo.
echo Please wait for the download to complete.
echo Save the file to your desired location.
echo.

:FINISH
echo.
echo ========================================
echo    Installation Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Make sure the downloaded file is saved
echo 2. Run 'create_browser.py' with Python
echo 3. Enjoy Glitch Create Browser!
echo.
echo To run the browser, use:
echo    python create_browser.py
echo.
echo Press any key to exit...
pause >nul
exit