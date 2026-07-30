import xml.etree.ElementTree as ET
import re
import sys
import argparse
from pathlib import Path

def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", name).strip() or "Unnamed"

def get_item_name(item: ET.Element) -> str:
    properties = item.find("Properties")
    if properties is not None:
        name_tag = properties.find("string[@name='Name']")
        if name_tag is not None and name_tag.text:
            return sanitize_filename(name_tag.text)
    return f"Unnamed_{item.attrib.get('class', 'Item')}"

def extract_luau_scripts(rbxmx_path: str | Path, output_dir: str | Path = None) -> None:
    rbxmx_path = Path(rbxmx_path)

    if not rbxmx_path.exists() or not rbxmx_path.is_file():
        print(f"\n[!] Error: Could not find '{rbxmx_path}'")
        sys.exit(1)

    try:
        tree = ET.parse(rbxmx_path)
        root = tree.getroot()
    except Exception as e:
        print(f"\n[!] Failed to parse XML: {e}")
        sys.exit(1)

    if not output_dir:
        first_item = root.find("Item")
        if first_item is not None:
            output_dir = get_item_name(first_item)
        else:
            output_dir = rbxmx_path.stem

    base_path = Path(output_dir).resolve()

    try:
        base_path.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        print(f"\n[!] Permission Denied: Windows blocked the script from creating folders at:\n    {base_path}")
        print("\nFixes:")
        print(" 1. Check if a FILE (not a folder) named exactly that already exists and delete it.")
        print(" 2. Windows Defender 'Controlled Folder Access' might be blocking Python.")
        print(" 3. Try providing a specific output path like: -o C:\\Users\\lz4\\Downloads\\Extracted")
        sys.exit(1)
    except Exception as e:
        print(f"\n[!] Failed to create output directory: {e}")
        sys.exit(1)

    script_extensions = {
        "Script": ".server.lua",
        "LocalScript": ".client.lua",
        "ModuleScript": ".lua"
    }

    extracted_count = 0

    def walk_tree(node: ET.Element, current_path: Path):
        nonlocal extracted_count

        if node.tag == "Item":
            item_class = node.attrib.get("class")
            item_name = get_item_name(node)
            next_path = current_path / item_name

            if item_class in ["Model", "Folder"]:
                next_path.mkdir(parents=True, exist_ok=True)

            if item_class in script_extensions:
                properties = node.find("Properties")
                
                source_tag = properties.find("ProtectedString[@name='Source']")
                if source_tag is None:
                    source_tag = properties.find("string[@name='Source']")
                
                script_source = source_tag.text if (source_tag is not None and source_tag.text) else ""
                
                current_path.mkdir(parents=True, exist_ok=True)
                
                file_ext = script_extensions[item_class]
                file_path = current_path / f"{item_name}{file_ext}"
                
                counter = 1
                while file_path.exists():
                    file_path = current_path / f"{item_name}_{counter}{file_ext}"
                    counter += 1

                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(script_source.strip() + "\n")
                
                print(f" [+] Extracted: {file_path.relative_to(base_path.parent)}")
                extracted_count += 1
        else:
            next_path = current_path

        for child in node:
            if child.tag == "Item":
                walk_tree(child, next_path)

    print(f"\nScanning '{rbxmx_path.name}'...")
    walk_tree(root, base_path)
    
    if extracted_count > 0:
        print(f"\n[✓] Success! Extracted {extracted_count} scripts into '{base_path}'")
    else:
        print(f"\n[-] No scripts were found inside '{rbxmx_path.name}'.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input")
    parser.add_argument("-o", "--output")
    
    args = parser.parse_args()

    if not args.input:
        user_input = input("Enter the path to your .rbxmx or .rbxlx file: ").strip().strip('"').strip("'")
        if not user_input:
            sys.exit(0)
        args.input = user_input

    extract_luau_scripts(args.input, args.output)

if __name__ == "__main__":
    main()
