#!/usr/bin/env python3
"""
Script to generate requirements.txt from pyproject.toml

Usage:
    python generate_requirements.py
"""

import re

def main():
    try:
        with open('pyproject.toml', 'r') as f:
            content = f.read()
        
        # Find dependencies using regex
        deps = re.findall(r'\"([^\"]+)>=([^\"]+)\"', content)
        
        # Generate requirements.txt content
        requirements = '\n'.join([f"{pkg}>={ver}" for pkg, ver in deps])
        
        # Write to requirements.txt
        with open('requirements.txt', 'w') as f:
            f.write(requirements)
            
        print("Successfully generated requirements.txt from pyproject.toml")
        
    except Exception as e:
        print(f"Error generating requirements.txt: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main()