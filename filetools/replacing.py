import csv
import os
import sys
from shutil import copyfile
from typing import Dict, List, OrderedDict, Union

import ffmpeg

__all__ = ["replace", "replace_playlists", "folders_to_playlist"]

from filetools.helpers import file_has_ext


def replace(reverse=False):
    csv_filename = "mapping.csv"
    csv.register_dialect('semicolon', delimiter=';', lineterminator='\r\n')
    with open(csv_filename, "r", encoding="utf-8") as csv_file:
        reader = csv.reader(csv_file, dialect='semicolon')
        for row in reader:
            old, new = row[:2]
            if reverse:
                new, old = old, new
            for (dirpath, dirnames, filenames) in os.walk(os.getcwd()):
                for filename in filenames:
                    if filename == csv_filename:
                        continue
                    outlines = []
                    with open(filename, "r", encoding="utf-8") as file:
                        for line in file:
                            if not line.startswith('#'):
                                line = line.replace(old, new)
                            outlines.append(line)
                    with open(filename, "w", encoding="utf-8") as file:
                        file.writelines(outlines)


def replace_playlists(output: str, include_only="", convert=True, copy=False, source_key="PC",
                      convertible_ext=(".m4a", ".flac", ".wav")):
    """
    prepare playlist for different destination
    :param output:
        column for output destination
    :param include_only:
        which playlist files should be included - if empty, all are included
    :param convert:
        optional feature to convert to mp3 if output is old IPod
        note: uses ffmpeg (ffmpeg-python). Ensure ffmpeg/ffprobe are installed and on PATH.
        download: https://www.gyan.dev/ffmpeg/builds/
        put into path in start script: os.environ["PATH"] += os.pathsep + r"C:\Program Files\ffmpeg\bin"
    :param copy:
        copy to new path
    :param source_key:
        valid path on PC where this is executed
    :param convertible_ext:
        extension that should be converted to mp3
    :return:
    """
    print(sys.getfilesystemencoding())
    cwd = os.getcwd()
    out_dir = os.path.join(cwd, output)
    os.makedirs(out_dir, exist_ok=True)
    all_lines = []
    csv_filename = "mapping.csv"
    mapping_rows = _read_mapping(csv_filename)
    for (dirpath, dirnames, filenames) in os.walk(cwd):
        if not dirpath == cwd:
            break
        for filename in filenames:
            if filename == csv_filename:
                continue
            if include_only and include_only not in filename:
                continue
            outlines = []
            with open(filename, "r", encoding="utf-8") as file:
                for line in file:
                    if not line.startswith('#'):
                        name_org = line.strip()
                        if os.path.isfile(name_org):
                            entries_for_replace = [
                                row for row in mapping_rows if row[source_key] in line]
                            if len(entries_for_replace) != 0:
                                row = entries_for_replace[0]
                                if not row[output]:
                                    row[output] = row[source_key]
                                if output == "IPod":
                                    fileext = name_org[name_org.rfind("."):]
                                    if fileext in convertible_ext:
                                        line = row[output] + \
                                            line[line.rfind(os.path.sep) + 1:]
                                        line = line.replace(fileext, ".mp3")
                                        name_dest = line.strip()
                                        if convert and not os.path.isfile(name_dest):
                                            print("convert to mp3: ", name_dest)
                                            os.makedirs(os.path.dirname(
                                                name_dest), exist_ok=True)
                                            try:
                                                # convert and copy metadata
                                                inp = ffmpeg.input(name_org)
                                                out = ffmpeg.output(
                                                    inp, name_dest, format='mp3', audio_bitrate='320k', map_metadata=0)
                                                ffmpeg.run(
                                                    out, overwrite_output=True)
                                            except ffmpeg.Error as e:
                                                print(
                                                    "ffmpeg conversion failed:", e)
                                else:
                                    line = row[output] + \
                                        line[line.rfind(os.path.sep) + 1:]
                                if copy:
                                    name_dest = line.strip()
                                    if not row[output] == row[source_key] and not os.path.isfile(name_dest):
                                        os.makedirs(os.path.dirname(
                                            name_dest), exist_ok=True)
                                        print('copy: ', name_org, name_dest)
                                        copyfile(name_org, name_dest)
                            else:
                                print(
                                    'warning - destination not configured: ', line)
                        else:
                            print('warning - does not exist: ',
                                  filename, name_org)
                    if line not in outlines:
                        outlines.append(line)
                    if line not in all_lines:
                        all_lines.append(line)
            _create_file(out_dir, filename, outlines)
            _create_wpl_file(os.path.join(out_dir, filename), outlines)

    _create_file(output, "combined.m3u8", all_lines)
    _create_wpl_file(os.path.join(out_dir, "combined"), all_lines)


def _read_mapping(csv_filename: str) -> List[Union[Dict[str, str], OrderedDict[str, str]]]:
    csv.register_dialect('semicolon', delimiter=';', lineterminator='\r\n')
    with open(csv_filename, "r", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file, dialect='semicolon')
        return [row for row in reader]


def _create_file(out_dir, filename, outlines):
    with open(os.path.join(out_dir, filename), "w", encoding="utf-8") as file:
        file.writelines(outlines)


def _create_wpl_file(out_filename: str, outlines: List[str]):
    out_filename = out_filename[:out_filename.rfind('.')]
    title = out_filename[out_filename.rfind(os.path.sep) + 1:]
    with open(out_filename + ".wpl", "w", encoding="utf-8") as file:
        file.write('<?wpl version="1.0"?>\n')
        file.write('<smil><head><author/>\n')
        file.write('<title>' + title + '</title>\n')
        file.write('</head><body><seq>\n')
        for line in outlines:
            if not line.startswith('#'):
                file.write('<media src="' + line.strip() + '"/>\n')
        file.write('</seq></body></smil>\n')


def folders_to_playlist():
    cwd = os.getcwd()
    out_dir = os.path.join(cwd, "playlists")
    os.makedirs(out_dir, exist_ok=True)
    all_lines = []
    for (dirpath, dirnames, filenames) in os.walk(cwd):
        basename = os.path.basename(dirpath)
        outlines = [os.path.join(dirpath, filename + "\n") for filename in filenames if
                    file_has_ext(filename, ['.mp3', '.m4a', '.mp4', '.flv'])]
        if not outlines:
            continue
        playlist_name = os.path.join(out_dir, basename + ".m3u8")
        _create_file(out_dir, basename + ".m3u8", outlines)
        _create_wpl_file(playlist_name, outlines)
        all_lines += outlines
    all_lines.sort()
    _create_file(out_dir, "combined.m3u8", all_lines)


def _ext_to_format(ext: str):
    if ext in ['m4a', 'mp4']:
        return "mp4"
    return ext


def normalize():
    cwd = os.getcwd()
    for (dirpath, dirnames, filenames) in os.walk(cwd):
        basename = os.path.basename(dirpath)
        out_dir = os.path.join("output", os.path.relpath(dirpath, cwd))
        os.makedirs(out_dir, exist_ok=True)
        for filename in filenames:
            if not file_has_ext(filename, ['.mp3', '.m4a', '.mp4', '.flv']):
                continue
            ext = filename[filename.rfind(".") + 1:]
            inp = os.path.join(dirpath, filename)
            outp = os.path.join(out_dir, filename)
            try:
                stream = ffmpeg.input(inp)
                # loudnorm filter normalizes audio levels; adjust params if needed
                stream = stream.filter('loudnorm')
                out = ffmpeg.output(stream, outp, format=_ext_to_format(
                    ext), audio_bitrate='260k', map_metadata=0)
                ffmpeg.run(out, overwrite_output=True)
            except ffmpeg.Error as e:
                print('ffmpeg normalization failed for', inp, e)
