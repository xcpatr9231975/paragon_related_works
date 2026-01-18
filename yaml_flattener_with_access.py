import yaml
import json
import csv

def yaml_to_flattened_database(yaml_file_or_string, output_format='all', output_prefix='yaml_flat'):
    """
    Read YAML, flatten it, and dump with access instructions

    Args:
        yaml_file_or_string: Path to YAML file or YAML string
        output_format: 'screen', 'file', 'json', 'csv', or 'all'
        output_prefix: Prefix for output files

    Returns:
        dict: Contains flattened data and access instructions
    """

    
    # Load YAML
    print("\nINSIDE FLAT PY DEF YAML_TO_FLAT=:") 
    if yaml_file_or_string.endswith('.yaml') or yaml_file_or_string.endswith('.yml'):
        with open(yaml_file_or_string, 'r') as f:
            data = yaml.safe_load(f)
    else:
        data = yaml.safe_load(yaml_file_or_string)

    # Flatten function
    def flatten_yaml(d, parent_key='', sep='.'):
        items = []
        access_map = []

        def _recurse(obj, parent=''):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    new_key = f"{parent}{sep}{k}" if parent else k
                    if isinstance(v, (dict, list)):
                        _recurse(v, new_key)
                    else:
                        items.append((new_key, v))
                        # Generate access code
                        access_code = generate_access_code(new_key, sep)
                        access_map.append({
                            'flat_key': new_key,
                            'value': v,
                            'type': type(v).__name__,
                            'access_code': access_code
                        })
            elif isinstance(obj, list):
                for idx, item in enumerate(obj):
                    new_key = f"{parent}[{idx}]"
                    if isinstance(item, (dict, list)):
                        _recurse(item, new_key)
                    else:
                        items.append((new_key, item))
                        access_code = generate_access_code(new_key, sep)
                        access_map.append({
                            'flat_key': new_key,
                            'value': item,
                            'type': type(item).__name__,
                            'access_code': access_code
                        })

        _recurse(d)
        return dict(items), access_map

    def generate_access_code(flat_key, sep):
        """Generate Python code to access the value"""
        parts = flat_key.replace(sep, "']['").split('[')
        code = "data"

        for part in parts:
            if part:
                if ']' in part:
                    idx, rest = part.split(']', 1)
                    code += f"[{idx}]"
                    if rest and rest.startswith("']['"):
                        code += f"['{rest[3:]}'']"
                else:
                    code += f"['{part}']"

        return code.replace("''", "'")

    flattened_dict, access_list = flatten_yaml(data)

    # Output to screen
    if output_format in ['screen', 'all']:
        print("=" * 80)
        print("FLATTENED YAML DATABASE")
        print("=" * 80)
        print(f"Total Items: {len(flattened_dict)}\n")

        print(f"{'FLAT KEY':<50} {'VALUE':<25} {'TYPE':<10}")
        print("-" * 85)
        for key, value in flattened_dict.items():
            val_str = str(value)[:23] + '..' if len(str(value)) > 25 else str(value)
            print(f"{key:<50} {val_str:<25} {type(value).__name__:<10}")

        print("\n" + "=" * 80)
        print("HOW TO ACCESS EACH ITEM")
        print("=" * 80)
        for item in access_list[:10]:
            print(f"# {item['flat_key']}")
            print(f"{item['access_code']}  # => {repr(item['value'])}")
            print()
        if len(access_list) > 10:
            print(f"... (showing 10 of {len(access_list)} items)")
        print()

    # Output to text file
    if output_format in ['file', 'all']:
        with open(f'{output_prefix}_access_guide.txt', 'w') as f:
            f.write("FLATTENED YAML DATABASE - ACCESS GUIDE\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Total Items: {len(flattened_dict)}\n\n")

            for item in access_list:
                f.write(f"Flat Key: {item['flat_key']}\n")
                f.write(f"Access:   {item['access_code']}\n")
                f.write(f"Value:    {repr(item['value'])} ({item['type']})\n")
                f.write("-" * 80 + "\n")

        print(f"✓ Saved access guide to: {output_prefix}_access_guide.txt")

    # Output to JSON
    if output_format in ['json', 'all']:
        output_data = {
            'flattened': flattened_dict,
            'access_map': access_list
        }
        with open(f'{output_prefix}.json', 'w') as f:
            json.dump(output_data, f, indent=2)

        print(f"✓ Saved JSON database to: {output_prefix}.json")

    # Output to CSV
    if output_format in ['csv', 'all']:
        with open(f'{output_prefix}.csv', 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Flat Key', 'Value', 'Type', 'Access Code'])
            for item in access_list:
                writer.writerow([
                    item['flat_key'],
                    item['value'],
                    item['type'],
                    item['access_code']
                ])

        print(f"✓ Saved CSV database to: {output_prefix}.csv")

    return {
        'original': data,
        'flattened': flattened_dict,
        'access_map': access_list
    }


# Example usage
if __name__ == '__main__':
    #sample_yaml = """
    #application:
    #  name: MyApp
    #  settings:
    #    timeout: 30
    #devices:
    #  - hostname: router-01
    #    ip: 192.168.1.1
    #"""

    # Use the function
    print("\n==START Direct access examples:")
    result = yaml_to_flattened_database(sample_yaml, output_format='all')
    print("\n==END Direct access examples:") 

    # Access examples
    #print("\nDirect access examples:")
    #data = result['original']
    #print(f"App name: {data['application']['name']}")
    #print(f"Device IP: {data['devices'][0]['ip']}")
