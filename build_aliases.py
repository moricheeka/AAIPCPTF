
#!/usr/bin/env python3
"""Utility to regenerate taxonomy_aliases.json from taxonomy_index.json.

Usage:
    python build_aliases.py [-i TAXONOMY_INDEX] [-o OUTPUT_JSON]

Defaults:
    TAXONOMY_INDEX = taxonomy_index.json
    OUTPUT_JSON    = taxonomy_aliases.json
"""
import argparse, json, re, os, sys, textwrap
from collections import defaultdict

ABBREV_TABLE = {
    "science fiction": ["sci-fi", "scifi"],
    "information technology": ["it"],
    "artificial intelligence": ["ai"],
    "public relations": ["pr"],
    "corporate communications": ["corp comms", "corporate comms"],
    "user interface": ["ui"],
    "user experience": ["ux"],
    "non-disclosure agreements (ndas)": ["nda", "non disclosure agreement", "non disclosure agreements"],
    "terms & conditions": ["t&c", "terms and conditions"],
    "frequently asked questions": ["faq", "faqs"],
}

def hyphen_variants(label: str):
    if '-' in label:
        yield label.replace('-', ' ')
    if ' ' in label:
        yield label.replace(' ', '-')

def ampersand_variants(label: str):
    if '&' in label:
        yield label.replace('&', 'and')
    if ' and ' in label:
        yield label.replace(' and ', ' & ')

def plural_variants(label: str):
    words = label.split()
    last = words[-1]
    if last.endswith('s') and len(last) > 3:
        yield ' '.join(words[:-1] + [last[:-1]])
    else:
        yield ' '.join(words[:-1] + [last + 's'])

def generate_aliases(index_map):
    alias_map = {}
    for label, path in index_map.items():
        variants = set()
        variants.add(label)
        variants.add(label.title())
        variants.update(hyphen_variants(label))
        variants.update(ampersand_variants(label))
        variants.update(plural_variants(label))
        if label in ABBREV_TABLE:
            variants.update(ABBREV_TABLE[label])
        for v in variants:
            alias_map[v.lower()] = path
    return alias_map

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-i', '--index', default='taxonomy_index.json')
    ap.add_argument('-o', '--output', default='taxonomy_aliases.json')
    args = ap.parse_args()

    if not os.path.isfile(args.index):
        sys.exit(f"Taxonomy index file '{args.index}' not found.")
    with open(args.index, 'r', encoding='utf-8') as f:
        index_map = json.load(f)

    alias_map = generate_aliases(index_map)
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(alias_map, f, indent=2, ensure_ascii=False)

    print(f"Generated {len(alias_map)} aliases → {args.output}")

if __name__ == '__main__':
    main()
