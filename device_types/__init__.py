import os
import ast
import importlib
import inspect
from pathlib import Path
from typing import List

# Directory containing device modules
current_dir = os.path.dirname(__file__)
__all__: List[str] = []

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

# Temporary storage for exported names
exported_names: List[str] = []

for filename in os.listdir(current_dir):
    if filename.endswith(".py") and filename != "__init__.py":
        module_name = filename[:-3]  # remove .py
        module = importlib.import_module(f".{module_name}", package=__name__)

        # Add all functions and classes from the module to package namespace
        for name, obj in inspect.getmembers(module):
            if inspect.isfunction(obj) or inspect.isclass(obj):
                globals()[name] = obj
                exported_names.append(name)  # Now Pylance knows __all__ is a list of str

for py_file in directory.glob("*.py"):
    if py_file.name != "__init__.py":
        classes = extract_class_names(py_file)
        all_classes[py_file.stem] = classes

__all__ = ["all_classes", "exported_names"]

# Print results
print("All Classes:", all_classes)
# print("Imported Modules:", imported_modules)