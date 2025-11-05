@echo off
:: Change working directory to project root (one level above this windows folder)
set ROOT=%~dp0..
:: Activate the virtual environment located at %ROOT%\.venv
call "%ROOT%\.venv\Scripts\activate"
:: Run the app
python "%ROOT%\src\main.py"