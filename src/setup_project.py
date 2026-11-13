# This python file simply does the early steps of creating folders in Github.
# 1) Recreate the full project directory structure
# 2) Make sure all core folders exist
# 3) Print the structure so you know everything is ready
# Idea is to make this project easily reproducible 

import os 
from datetime import datetime

def create_folders():
    folders = [
        "data",
        "data/bronze",
        "data/silver",
        "data/gold",
        "data/archive",
        "logs",
        "config",
        "src",
        "database"
    ]
# Fixed Indentation issue in below for folder line
    for folder in folders:
        os.makedirs(folder, exist_ok=True)
        print(f"[OK] Folder ready: {folder}")
def show_structure():
    for root, dirs, files in os.walk("."):
        print(root)
        for d in dirs:
            print(f"  ┗ {d}/")
def main():
    print("Starting project setup...")
    print(f"Time: {datetime.now()}")
    create_folders()
    print("\nProject structure:")
    show_structure()
    print("\nSetup completed successfully.")
if __name__ == "__main__":
    main()
