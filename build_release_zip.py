import os
import zipfile

PLUGIN_DIR_NAME = 'astrbot_plugin_gaokao'
ZIP_NAME = 'astrbot_plugin_gaokao_v5.zip'

files_to_zip = [
    'main.py',
    '_conf_schema.json',
    'metadata.yaml'
]

print(f"Building {ZIP_NAME} with explicit root directory entry...")

with zipfile.ZipFile(ZIP_NAME, 'w', zipfile.ZIP_DEFLATED) as zf:
    # ASTRBOT WORKAROUND: The very first entry in the ZIP *must* be the plugin's root directory.
    # AstrBot uses `namelist()[0]` to determine what to copy, so if the first entry is a file, 
    # it fails with Errno 20 (Not a directory).
    root_info = zipfile.ZipInfo(f"{PLUGIN_DIR_NAME}/")
    zf.writestr(root_info, b'')
    print(f"Added explicit root directory: {PLUGIN_DIR_NAME}/")

    # Add main files
    for f in files_to_zip:
        if os.path.exists(f):
            arcname = f"{PLUGIN_DIR_NAME}/{f}"
            print(f"Adding {f} -> {arcname}")
            zf.write(f, arcname)
        else:
            print(f"WARNING: {f} not found!")

    # Add Data directory
    data_count = 0
    for root, dirs, files in os.walk('Data'):
        for file in files:
            if file.endswith('.json'):
                full_path = os.path.join(root, file)
                arcname = f"{PLUGIN_DIR_NAME}/{full_path.replace(os.sep, '/')}"
                zf.write(full_path, arcname)
                data_count += 1
    print(f"Added {data_count} data files.")

# Verify the ZIP structure, especially the first entry!
with zipfile.ZipFile(ZIP_NAME, 'r') as zf:
    names = zf.namelist()
    print(f"\nVerification - {len(names)} entries:")
    print(f"FIRST ENTRY (CRITICAL): '{names[0]}'")
    assert names[0] == f"{PLUGIN_DIR_NAME}/", "ERROR: First entry is NOT the root directory!"
    print("\n✓ ZIP structure is correct for AstrBot deployment!")

print(f"\nDone! Created {ZIP_NAME}")
