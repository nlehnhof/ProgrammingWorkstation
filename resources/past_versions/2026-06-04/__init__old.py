import os
import ast
import importlib.util
from pathlib import Path

# Directory containing device modules
current_dir = os.path.dirname(__file__)

# Function to extract class names from a Python file
def extract_class_names(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        file_contents = f.read()
    tree = ast.parse(file_contents)
    class_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    return class_names

# Example usage: extract class names from multiple Python files
directory = Path("./device_types")  # folder containing Python files
all_classes = {}  # Dictionary to store class names per file
imported_modules = {}  # Dictionary to store imported modules if needed

for py_file in directory.glob("*.py"):
    classes = extract_class_names(py_file)
    all_classes[py_file.stem] = classes

# Print results
print("Extracted Classes:", all_classes)
# print("Imported Modules:", imported_modules)