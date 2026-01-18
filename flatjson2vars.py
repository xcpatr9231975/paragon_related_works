#!/usr/bin/env python3
"""
FlatJSON2Vars - Convert flattened JSON key-value pairs to Python variables
Author: Generated for network automation use cases
Version: 1.0

This library provides multiple approaches to convert flattened JSON structures
into directly accessible Python variables using dot notation.
"""

import json
from types import SimpleNamespace
from typing import Any, Dict


class DotDict(dict):
    """
    Dictionary subclass that allows dot notation access to keys.

    Example:
        d = DotDict({'router': {'ip': '10.0.0.1'}})
        print(d.router.ip)  # '10.0.0.1'
    """

    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

    def __init__(self, data: dict):
        super().__init__(data)
        for key, value in data.items():
            if isinstance(value, dict):
                self[key] = DotDict(value)
            elif isinstance(value, list):
                self[key] = [DotDict(item) if isinstance(item, dict) else item for item in value]


class Bunch:
    """
    Simple class that converts dictionary to object with attribute access.

    Example:
        b = Bunch({'name': 'router1', 'ip': '10.0.0.1'})
        print(b.name)  # 'router1'
    """

    def __init__(self, data: dict):
        self.__dict__.update(data)

    def __repr__(self):
        items = (f"{k}={v!r}" for k, v in self.__dict__.items())
        return f"{self.__class__.__name__}({', '.join(items)})"


class FlatJSONConverter:
    """
    Main converter class for flattened JSON to variables.
    Supports multiple output formats and access patterns.
    """

    @staticmethod
    def unflatten(flat_dict: Dict[str, Any], separator: str = '.') -> Dict:
        """
        Convert flattened dictionary back to nested structure.

        Args:
            flat_dict: Flattened dictionary with dot-separated keys
            separator: Key separator (default: '.')

        Returns:
            Nested dictionary

        Example:
            flat = {'router.r0.ip': '10.0.0.1'}
            nested = unflatten(flat)
            # {'router': {'r0': {'ip': '10.0.0.1'}}}
        """
        result = {}

        for key, value in flat_dict.items():
            parts = key.split(separator)
            current = result

            for i, part in enumerate(parts[:-1]):
                # Handle array indices
                if part.endswith(']'):
                    base_key = part[:part.index('[')]
                    index = int(part[part.index('[')+1:part.index(']')])

                    if base_key not in current:
                        current[base_key] = []

                    while len(current[base_key]) <= index:
                        current[base_key].append({})

                    current = current[base_key][index]
                else:
                    if part not in current:
                        current[part] = {}
                    current = current[part]

            # Set the final value
            final_key = parts[-1]
            if final_key.endswith(']'):
                base_key = final_key[:final_key.index('[')]
                index = int(final_key[final_key.index('[')+1:final_key.index(']')])

                if base_key not in current:
                    current[base_key] = []

                while len(current[base_key]) <= index:
                    current[base_key].append(None)

                current[base_key][index] = value
            else:
                current[final_key] = value

        return result

    @staticmethod
    def to_dotdict(flat_dict: Dict[str, Any], unflatten: bool = True) -> DotDict:
        """
        Convert flattened dictionary to DotDict with dot notation access.

        Args:
            flat_dict: Flattened dictionary
            unflatten: Whether to unflatten first (default: True)

        Returns:
            DotDict object with dot notation access
        """
        if unflatten:
            nested = FlatJSONConverter.unflatten(flat_dict)
            return DotDict(nested)
        return DotDict(flat_dict)

    @staticmethod
    def to_namespace(flat_dict: Dict[str, Any], unflatten: bool = True) -> SimpleNamespace:
        """
        Convert flattened dictionary to SimpleNamespace (Python 3.3+).

        Args:
            flat_dict: Flattened dictionary
            unflatten: Whether to unflatten first (default: True)

        Returns:
            SimpleNamespace object with attribute access
        """
        if unflatten:
            nested = FlatJSONConverter.unflatten(flat_dict)
            return json.loads(json.dumps(nested), object_hook=lambda d: SimpleNamespace(**d))
        return SimpleNamespace(**flat_dict)

    @staticmethod
    def to_bunch(flat_dict: Dict[str, Any], unflatten: bool = True) -> Bunch:
        """
        Convert flattened dictionary to Bunch object.

        Args:
            flat_dict: Flattened dictionary
            unflatten: Whether to unflatten first (default: True)

        Returns:
            Bunch object with attribute access
        """
        if unflatten:
            nested = FlatJSONConverter.unflatten(flat_dict)
            return Bunch(nested)
        return Bunch(flat_dict)

    @staticmethod
    def to_variables(flat_dict: Dict[str, Any], sanitize_keys: bool = True) -> Dict[str, Any]:
        """
        Convert flattened dictionary to simple variables (returns dict for unpacking).

        Args:
            flat_dict: Flattened dictionary
            sanitize_keys: Replace dots with underscores for valid Python identifiers

        Returns:
            Dictionary with sanitized keys for variable unpacking

        Example:
            vars_dict = to_variables(flat_dict)
            locals().update(vars_dict)
            # Now you can use variables directly
        """
        if sanitize_keys:
            return {key.replace('.', '_'): value for key, value in flat_dict.items()}
        return flat_dict


def load_flattened_json(filepath: str, mode: str = 'dotdict') -> Any:
    """
    Load flattened JSON file and convert to specified format.

    Args:
        filepath: Path to JSON file
        mode: Conversion mode - 'dotdict', 'namespace', 'bunch', 'variables', 'dict'

    Returns:
        Converted data structure based on mode

    Example:
        # Load and access with dot notation
        data = load_flattened_json('config.json', mode='dotdict')
        print(data.routers.r0.interfaces.interface_C.connects_to.interface)
    """
    with open(filepath, 'r') as f:
        json_data = json.load(f)

    # Check if it has a 'flattened' key
    if 'flattened' in json_data:
        flat_dict = json_data['flattened']
    else:
        flat_dict = json_data

    converter = FlatJSONConverter()

    if mode == 'dotdict':
        return converter.to_dotdict(flat_dict)
    elif mode == 'namespace':
        return converter.to_namespace(flat_dict)
    elif mode == 'bunch':
        return converter.to_bunch(flat_dict)
    elif mode == 'variables':
        return converter.to_variables(flat_dict)
    elif mode == 'dict':
        return converter.unflatten(flat_dict)
    else:
        raise ValueError(f"Unknown mode: {mode}. Use 'dotdict', 'namespace', 'bunch', 'variables', or 'dict'")


# Convenience function
def flatten_to_vars(json_filepath: str) -> SimpleNamespace:
    """
    Quick function to load flattened JSON and return as SimpleNamespace.

    Args:
        json_filepath: Path to JSON file

    Returns:
        SimpleNamespace with dot notation access

    Example:
        config = flatten_to_vars('yaml_flat.json')
        print(config.routers.r0.ip)
    """
    return load_flattened_json(json_filepath, mode='namespace')


if __name__ == "__main__":
    # Example usage
    print("FlatJSON2Vars Library - Example Usage")
    print("=" * 70)

    # Sample flattened data
    sample_flat = {
        "routers.r0.ip": "10.161.32.178",
        "routers.r0.name": "riyadh",
        "routers.r0.interfaces.interface_C.ip_address": "192.168.2.1/30",
        "routers.r0.interfaces.interface_C.connects_to.interface": "interface_D"
    }

    print("\nOriginal flattened data:")
    for k, v in sample_flat.items():
        print(f"  {k}: {v}")

    print("\n" + "=" * 70)
    print("METHOD 1: DotDict (Recommended)")
    print("=" * 70)

    converter = FlatJSONConverter()
    data1 = converter.to_dotdict(sample_flat)
    print(f"Access: data.routers.r0.ip")
    print(f"Result: {data1.routers.r0.ip}")
    print(f"\nAccess: data.routers.r0.interfaces.interface_C.connects_to.interface")
    print(f"Result: {data1.routers.r0.interfaces.interface_C.connects_to.interface}")

    print("\n" + "=" * 70)
    print("METHOD 2: SimpleNamespace")
    print("=" * 70)

    data2 = converter.to_namespace(sample_flat)
    print(f"Access: data.routers.r0.name")
    print(f"Result: {data2.routers.r0.name}")

    print("\n" + "=" * 70)
    print("METHOD 3: Variables (for locals())")
    print("=" * 70)

    vars_dict = converter.to_variables(sample_flat)
    print("Sanitized variable names:")
    for key in list(vars_dict.keys())[:3]:
        print(f"  {key}: {vars_dict[key]}")
    print(f"  ... ({len(vars_dict)} total variables)")
