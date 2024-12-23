# a little tool to count inspect and compare keys

from pathlib import Path
import json

directory = Path.cwd() / Path('item-metadata')  # Replace with your directory
key_to_check = 'description'
key_to_compare = 'notes'

custom_key_count = 0
count = 0

for filepath in directory.glob('*.json'):
    with open(filepath, 'r') as file:
        try:
            data = json.load(file)
            data = data.get('item', data)
            count += 1
            key1 = data.get(key_to_check, None)
            key2 = data['item'].get(key_to_compare, None)
            with open('output.txt', 'a') as f:
                f.write(f'{filepath.name}:\n {key1} \n {key2} \n')

        except json.JSONDecodeError:
            print(f"Error decoding JSON in file {filepath.name}")

print(f"Number of files where '{key_to_check}' is the same as {key_to_compare}: {custom_key_count}")
print(f"Total number of files checked: {count}")

