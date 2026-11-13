# This python file simply does the early steps of creating folders in Github.
# Idea is to make this project easily reproducible 

import os --helps you create folders and navigate the file system.
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
