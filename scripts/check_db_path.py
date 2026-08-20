from pathlib import Path
import os

# Simulate the path calculation from main.py
current_file = Path("C:/Users/badza/Desktop/Sabrsl_dead_linker_Bot/backend/api/main.py")
project_root = current_file.parent.parent.parent
print(f"Calculated project_root: {project_root}")
print(f"Project root exists: {project_root.exists()}")

# Check database path
db_path = project_root / "data" / "wikipedia_maintenance.db"
print(f"Database path: {db_path}")
print(f"Database exists: {db_path.exists()}")

# Check actual structure
print(f"\nContents of project_root:")
if project_root.exists():
    for item in project_root.iterdir():
        print(f"  - {item.name}")

# Check if data directory exists
data_dir = project_root / "data"
print(f"\nData directory exists: {data_dir.exists()}")
if data_dir.exists():
    print(f"Contents of data directory:")
    for item in data_dir.iterdir():
        print(f"  - {item.name}")