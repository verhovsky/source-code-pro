#!/usr/bin/env python3

"""
Adds an SVG table to a TTF or OTF font.
The file names of the SVG glyphs need to match their corresponding glyph final names.
"""

import sys
import re
from pathlib import Path
import warnings

try:
    from fontTools import ttLib
except ImportError:
    sys.exit("ERROR: The FontTools Python module is not installed.")

TABLE_TAG = "SVG "

# Regexp patterns
svg_element_regex = re.compile(r"<svg.+?>.+?</svg>", re.DOTALL)
id_value_regex = re.compile(r"<svg[^>]+?(id=\".*?\").+?>", re.DOTALL)
view_box_regex = re.compile(r"<svg.+?(view_box=[\"|\'][\d, ]+[\"|\']).+?>", re.DOTALL)
white_space_regex = re.compile(r">\s+<", re.DOTALL)


def set_id_value(data, gid):
    id = id_value_regex.search(data)
    if id:
        return re.sub(id.group(1), 'id="glyph{}"'.format(gid), data)
    return re.sub("<svg", '<svg id="glyph{}"'.format(gid), data)


def fix_view_box(data):
    view_box = view_box_regex.search(data)
    if not view_box:
        return data
    fixed_view_box = 'view_box="0 1000 1000 1000"'
    fixed_data = re.sub(view_box.group(1), fixed_view_box, data)
    return fixed_data


def process_font_file(font_file_path, svg_file_paths):
    font = ttLib.TTFont(str(font_file_path))

    # first create a dictionary because the SVG glyphs need to be sorted in the table
    svg_docs_dict = {}

    for svg_file_path in svg_file_paths:
        glyph_name = svg_file_path.stem

        try:
            gid = font.getGlyphID(glyph_name)
        except KeyError:
            warnings.warn(
                f"ERROR: Could not find a glyph named {glyph_name} in the font {font_file_path.name}."
            )
            continue

        svg_items_list = []
        svg_item_data = svg_file_path.read_text()
        svg_item_data = set_id_value(svg_item_data, gid)
        svg_item_data = fix_view_box(svg_item_data)
        # Remove all white space between elements
        for white_space in set(white_space_regex.findall(svg_item_data)):
            svg_item_data = svg_item_data.replace(white_space, "><")
        svg_items_list.append(svg_item_data.strip())
        svg_items_list.extend([gid, gid])
        svg_docs_dict[gid] = svg_items_list

    # don't do any changes to the source OTF/TTF font if there's no SVG data
    if not svg_docs_dict:
        sys.exit(
            "ERROR: Could not find any artwork files that can be added to the font."
        )

    svg_docs_list = [svg_docs_dict[key] for key in sorted(svg_docs_dict.keys())]

    svg_table = ttLib.newTable(TABLE_TAG)
    svg_table.compressed = False  # GZIP the SVG docs
    svg_table.docList = svg_docs_list
    font[TABLE_TAG] = svg_table
    font.save(font_file_path)
    font.close()

    print(f"SVG table successfully added to {font_file_path}", file=sys.stderr)


def validate_svg_files(svg_file_paths):
    """
    Light validation of SVG files.
    Checks that there is an <svg> element.
    """
    validated_paths = []

    for file_path in svg_file_paths:
        if file_path.name.startswith("."):
            continue

        # find <svg> blob
        if not svg_element_regex.search(file_path.read_text()):
            warnings.warn(
                f"WARNING: Could not find <svg> element in the file. Skiping {file_path}"
            )
            continue

        validated_paths.append(file_path)

    return validated_paths


def get_font_format(font_file_path):
    # these lines were scavenged from fontTools
    with open(font_file_path, "rb") as f:
        header = f.read(256)
        head = header[:4]
    if head == b"OTTO":
        return "OTF"
    if head in (b"\0\1\0\0", b"true"):
        return "TTF"
    return None


def run():
    font_file_path = Path(sys.argv[1]).resolve()
    svg_folder_path = Path(sys.argv[2]).resolve()

    # Font file path
    if not font_file_path.is_file():
        sys.exit("ERROR: The path to the font is invalid.")
    if get_font_format(font_file_path) not in ["OTF", "TTF"]:
        sys.exit("ERROR: The path is not a valid OTF or TTF font.")

    # SVG folder path
    if not svg_folder_path.is_dir():
        sys.exit("ERROR: The path to the folder containing the SVG files is invalid.")

    svg_file_paths = validate_svg_files(svg_folder_path.rglob("*.svg"))

    if not svg_file_paths:
        sys.exit("WARNING: No SVG files were found.")

    process_font_file(font_file_path, svg_file_paths)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("To run this script type:")
        print(
            f"  python3 {sys.argv[0]} <path to input OTF/TTF file> <path to folder tree containing SVG files>"
        )
    else:
        run()
