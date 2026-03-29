import json
import glob
import random
import os

files = glob.glob('Data/*/*AGIEval*.json')
for f in files:
    with open(f, 'r', encoding='utf-8') as file:
        data = json.load(file)['example']
    
    source_tags = set(q.get('_source', '') for q in data)
    print(f"File: {os.path.basename(f)}")
    print(f"Total questions: {len(data)}")
    print("Sample sources:")
    for src in random.sample(list(source_tags), min(3, len(source_tags))):
        print(f"  - {src}")
    print()
