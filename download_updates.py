import os
import json
import urllib.request
import traceback

def download_files_from_github_api(repo_owner, repo_name, folder_path, dest_dir):
    api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{folder_path}"
    print(f"Fetching list from {api_url}")
    try:
        req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
        
        for item in data:
            if item['type'] == 'file' and item['name'].endswith('.json'):
                raw_url = item['download_url']
                dest_path = os.path.join(dest_dir, item['name'])
                print(f"Downloading {item['name']}...")
                req_file = urllib.request.Request(raw_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req_file) as file_resp:
                    with open(dest_path, 'wb') as f:
                        f.write(file_resp.read())
                print(f"Saved to {dest_path}")
    except Exception as e:
        print(f"Failed to process {folder_path}: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    base_dir = r"f:\project\ai\astrbot_plugin_cet6"
    obj_dir = os.path.join(base_dir, "Data", "Objective_Questions")
    
    os.makedirs(obj_dir, exist_ok=True)
    
    download_files_from_github_api("OpenLMLab", "GAOKAO-Bench-Updates", "Data/GAOKAO-Bench-2023", obj_dir)
    download_files_from_github_api("OpenLMLab", "GAOKAO-Bench-Updates", "Data/GAOKAO-Bench-2024", obj_dir)
    print("Download completed.")
