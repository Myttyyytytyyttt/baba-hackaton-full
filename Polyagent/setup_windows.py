#!/usr/bin/env python
"""
Setup script for Windows compatibility with PolyAgent
This script helps Windows users set up the environment correctly without uvloop dependency.
"""

import os
import sys
import subprocess
import platform
from colorama import init, Fore, Style

# Initialize colorama
init()

def print_header(message):
    print(f"\n{Fore.CYAN}==={Style.BRIGHT} {message} {Style.RESET_ALL}{Fore.CYAN}==={Style.RESET_ALL}\n")

def print_success(message):
    print(f"{Fore.GREEN}✓ {message}{Style.RESET_ALL}")

def print_error(message):
    print(f"{Fore.RED}✗ {message}{Style.RESET_ALL}")

def print_warning(message):
    print(f"{Fore.YELLOW}! {message}{Style.RESET_ALL}")

def print_info(message):
    print(f"{Fore.BLUE}ℹ {message}{Style.RESET_ALL}")

def run_command(command, error_message="Command failed"):
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        print_error(f"{error_message}: {e}")
        if e.stdout:
            print(f"Output: {e.stdout}")
        if e.stderr:
            print(f"Error: {e.stderr}")
        return False, None

def check_system():
    print_header("System Check")
    
    # Check if running on Windows
    if platform.system() != "Windows":
        print_warning("This script is intended for Windows systems only.")
        print_info(f"Detected system: {platform.system()}")
        proceed = input("Continue anyway? (y/n): ").strip().lower()
        if proceed != 'y':
            return False
    else:
        print_success(f"Windows detected: {platform.version()}")
    
    # Check Python version
    python_version = platform.python_version()
    print_info(f"Python version: {python_version}")
    if int(python_version.split('.')[0]) < 3 or int(python_version.split('.')[1]) < 8:
        print_warning("Python 3.8+ is recommended for this project.")
        proceed = input("Continue anyway? (y/n): ").strip().lower()
        if proceed != 'y':
            return False
    else:
        print_success("Python version is compatible")
    
    return True

def setup_environment():
    print_header("Setting Up Environment Variables")
    
    # Set up environment variables
    os.environ["PYTHONPATH"] = "."
    print_success("Set PYTHONPATH=.")
    
    # Check if .env file exists
    if not os.path.exists(".env"):
        print_warning("No .env file found. Creating example .env file.")
        with open(".env", "w") as f:
            f.write("# API Keys\n")
            f.write("PERPLEXITY_API_KEY=\n")
            f.write("POLYMARKET_API_KEY=\n")
            f.write("POLYGON_WALLET_PRIVATE_KEY=\n")
            f.write("DRY_RUN=true\n")
            f.write("USE_ASYNC=true\n")
        print_info("Created .env file. Please edit it to add your API keys.")
    else:
        print_success(".env file already exists")
    
    # Create bat file for easy running
    with open("run_polyagent.bat", "w") as f:
        f.write("@echo off\n")
        f.write("set PYTHONPATH=.\n")
        f.write("set USE_ASYNC=true\n") 
        f.write("python -m agents.application.trade\n")
        f.write("pause\n")
    print_success("Created run_polyagent.bat for easy execution")

def install_dependencies():
    print_header("Installing Dependencies")
    
    # Install dependencies without uvloop
    success, _ = run_command(
        "pip install -r requirements.txt",
        "Failed to install dependencies"
    )
    
    if not success:
        print_warning("Attempting alternative installation method without uvloop...")
        # Create a temporary requirements file without uvloop
        with open("requirements_win.txt", "w") as f:
            with open("requirements.txt", "r") as src:
                for line in src:
                    if "uvloop" not in line:
                        f.write(line)
        
        success, _ = run_command(
            "pip install -r requirements_win.txt",
            "Failed to install dependencies (alternative method)"
        )
        
        if os.path.exists("requirements_win.txt"):
            os.remove("requirements_win.txt")
    
    if success:
        print_success("Successfully installed dependencies")
    else:
        print_error("Failed to install dependencies")
        return False
    
    # Install spaCy model
    print_info("Installing spaCy model...")
    success, _ = run_command(
        "python -m spacy download en_core_web_sm",
        "Failed to install spaCy model"
    )
    
    if success:
        print_success("Successfully installed spaCy model")
    else:
        print_error("Failed to install spaCy model")
        return False
    
    return True

def main():
    print_header("PolyAgent Windows Setup")
    
    if not check_system():
        print_error("System check failed. Setup aborted.")
        return 1
    
    if not install_dependencies():
        print_error("Dependency installation failed. Setup aborted.")
        return 1
    
    setup_environment()
    
    print_header("Setup Complete")
    print_info("You can now run PolyAgent using the run_polyagent.bat file")
    print_info("Or run manually with: python -m agents.application.trade")
    print_info("Make sure to edit the .env file to add your API keys")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 