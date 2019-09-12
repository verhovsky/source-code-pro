#!/usr/bin/env python3

"""
Adds an SVG table to a TTF or OTF font.
The file names of the SVG glyphs need to match their corresponding glyph final names.
"""

import os
import sys
import re

try:
    from fontTools import ttLib, version
except ImportError:
    sys.exit("ERROR: FontTools Python module is not installed.")

TABLE_TAG = "SVG "

# Regexp patterns
svg_element_regex = re.compile(r"<svg.+?>.+?</svg>", re.DOTALL)
id_value_regex = re.compile(r"<svg[^>]+?(id=\".*?\").+?>", re.DOTALL)
view_box_regex = re.compile(r"<svg.+?(view_box=[\"|\'][\d, ]+[\"|\']).+?>", re.DOTALL)
white_space_regex = re.compile(r">\s+<", re.DOTALL)


def read_file(file_path):
    with open(file_path, "rt") as f:
        return f.read()


def set_id_value(data, gid):
    id = id_value_regex.search(data)
    if id:
        new_data = re.sub(id.group(1), 'id="glyph{}"'.format(gid), data)
    else:
        new_data = re.sub("<svg", '<svg id="glyph{}"'.format(gid), data)
    return new_data


def fix_view_box(data):
    view_box = view_box_regex.search(data)
    if not view_box:
        return data
    fixed_view_box = 'view_box="0 1000 1000 1000"'
    fixed_data = re.sub(view_box.group(1), fixed_view_box, data)
    return fixed_data


def get_glyph_name_from_file_name(file_path):
    folder_path, font_file_name = os.path.split(file_path)
    filename_no_extension, file_extension = os.path.splitext(font_file_name)
    return filename_no_extension


def process_font_file(font_file_path, svg_file_paths_list):
    font = ttLib.TTFont(font_file_path)

    # first create a dictionary because the SVG glyphs need to be sorted in the table
    svg_docs_dict = {}

    for svg_file_path in svg_file_paths_list:
        glyph_name = get_glyph_name_from_file_name(svg_file_path)

        try:
            gid = font.getGlyphID(glyph_name)
        except KeyError:
            print(
                "ERROR: Could not find a glyph named {} in the font {}.".format(
                    glyph_name, os.path.split(font_file_path)[1]
                ),
                file=sys.stderr,
            )
            continue

        svg_items_list = []
        svg_item_data = read_file(svg_file_path)
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
        print(
            "ERROR: Could not find any artwork files " "that can be added to the font.",
            file=sys.stderr,
        )
        return

    svg_docs_list = [svg_docs_dict[index] for index in sorted(svg_docs_dict.keys())]

    svg_table = ttLib.newTable(TABLE_TAG)
    svg_table.compressed = False  # GZIP the SVG docs
    svg_table.docList = svg_docs_list
    font[TABLE_TAG] = svg_table
    font.save(font_file_path)
    font.close()

    print("SVG table successfully added to {}".format(font_file_path), file=sys.stderr)


def validate_svg_files(svg_file_paths_list):
    """
    Light validation of SVG files.
    Checks that there is an <svg> element.
    """
    validated_paths = []

    for file_path in svg_file_paths_list:
        # skip hidden files (filenames that start with period)
        filename = os.path.basename(file_path)
        if filename[0] == ".":
            continue

        # read file
        data = read_file(file_path)

        # find <svg> blob
        svg = svg_element_regex.search(data)
        if not svg:
            print(
                "WARNING: Could not find <svg> element in the file. "
                "Skiping {}".format(file_path)
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
    elif head in (b"\0\1\0\0", b"true"):
        return "TTF"
    return None


def run():
    font_file_path = os.path.realpath(sys.argv[1])
    svg_folder_path = os.path.realpath(sys.argv[2])

    # Font file path
    if os.path.isfile(font_file_path):
        if get_font_format(font_file_path) not in ["OTF", "TTF"]:
            print("ERROR: The path is not a valid OTF or TTF font.", file=sys.stderr)
            return
    else:
        print("ERROR: The path to the font is invalid.", file=sys.stderr)
        return

    # SVG folder path
    if os.path.isdir(svg_folder_path):
        svg_file_paths_list = []
        for dir_name, subdir_list, file_list in os.walk(
            svg_folder_path
        ):  # Support nested folders
            for file in file_list:
                svg_file_paths_list.append(
                    os.path.join(dir_name, file)
                )  # Assemble the full paths, not just file names
    else:
        print(
            "ERROR: The path to the folder " "containing the SVG files is invalid.",
            file=sys.stderr,
        )
        return

    # validate the SVGs
    svg_file_paths_list = validate_svg_files(svg_file_paths_list)

    if not svg_file_paths_list:
        print("WARNING: No SVG files were found.", file=sys.stderr)
        return

    process_font_file(font_file_path, svg_file_paths_list)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(
            "To run this script type:\n  "
            "python {} <path to input OTF/TTF file>  "
            "<path to folder tree containing SVG files>".format(sys.argv[0])
        )
    else:
        run()
