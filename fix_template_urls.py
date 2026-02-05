#!/usr/bin/env python3
"""
Script to fix all URL references in LinkedIn templates to include namespace
"""
import re
import glob
import os

# Directory containing templates
TEMPLATE_DIR = "/Users/meetpatel/Desktop/Proc/Kaliagents/linkedin_automation/templates/linkedin_automation"

def fix_urls_in_file(filepath):
    """Fix URL tags in a single file"""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Pattern 1: {% url 'name' %} -> {% url 'linkedin_automation:name' %}
    content = re.sub(
        r"{%\s*url\s+'([^:][^']*)'\s*%}",
        r"{% url 'linkedin_automation:\1' %}",
        content
    )
    
    # Pattern 2: {% url "name" %} -> {% url "linkedin_automation:name" %}
    content = re.sub(
        r'{%\s*url\s+"([^:][^"]*)"\s*%}',
        r'{% url "linkedin_automation:\1" %}',
        content
    )
    
    # Pattern 3: {% url 'name' arg %} -> {% url 'linkedin_automation:name' arg %}
    content = re.sub(
        r"{%\s*url\s+'([^:][^']*)'(\s+[^%]+)%}",
        r"{% url 'linkedin_automation:\1'\2%}",
        content
    )
    
    # Pattern 4: {% url "name" arg %} -> {% url "linkedin_automation:name" arg %}
    content = re.sub(
        r'{%\s*url\s+"([^:][^"]*)"(\s+[^%]+)%}',
        r'{% url "linkedin_automation:\1"\2%}',
        content
    )
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    return filepath

if __name__ == "__main__":
    # Get all HTML files
    html_files = glob.glob(os.path.join(TEMPLATE_DIR, "*.html"))
    
    print(f"Processing {len(html_files)} template files...")
    for filepath in html_files:
        fix_urls_in_file(filepath)
        print(f"✓ Fixed {os.path.basename(filepath)}")
    
    print("\nAll templates updated successfully!")
