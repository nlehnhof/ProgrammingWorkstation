import os
import sys
import openpyxl
from openpyxl.styles import Font
from openpyxl.worksheet.hyperlink import Hyperlink
from resources.utilities.network_utils import is_valid_ip
from typing import Tuple, Optional

def get_excel_files(folder_path: str):
    print(f"Looking at path: {folder_path}...", flush=True)
    return [f for f in os.listdir(folder_path) if f.endswith(".xlsx") and f != "oshkosh_log.xlsx"]

def get_dropdown(filepath):
    gate_options = []
    print(filepath)
    
    try:
        wb = openpyxl.load_workbook(filepath)
        sheet = wb.active
        if sheet is None:
            return
        for row in sheet.iter_rows(min_row=2, max_col=5, values_only=True):
            value = row[4]
            if value is not None:
                gate_options.append(str(value))
                
    except Exception as e:
        print(f"Error Loading Dropdown Options: {e}")
        
    return gate_options


def lookup_excel(sheet, gate) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    file_path = sheet
    to_find = gate

    gate_ip: Optional[str] = None
    gate_netmask: Optional[str] = None
    gate_gateway: Optional[str] = None

    try:
        wb = openpyxl.load_workbook(file_path)
        sheet = wb.active
        if sheet is None:
            return gate_ip, gate_netmask, gate_gateway
        
        for row in sheet.iter_rows(values_only=True):
            for idx, cell in enumerate(row):
                if str(cell) == to_find and idx >= 3:
                    if idx + 1 < len(row) and row[idx + 1] is not None:
                        gate_ip = str(row[idx - 3]) if row[idx - 3] is not None else None
                        gate_netmask = str(row[idx - 2]) if row[idx - 2] is not None else None
                        gate_gateway = str(row[idx - 1]) if row[idx - 1] is not None else None
                        print(f"Gate IP: {gate_ip}")
                        print(f"Netmask: {gate_netmask}")
                        print(f"Gateway: {gate_gateway}")
                        return gate_ip, gate_netmask, gate_gateway
        return gate_ip, gate_netmask, gate_gateway            
    except Exception as e:
        print(f"Error Reading File: {e}")
        return gate_ip, gate_netmask, gate_gateway            




