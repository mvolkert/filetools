import datetime
import os
import re
from typing import List, Iterable

from natsort import natsorted


def renameInPlace(dirpath, oldFilename, newFilename):
    os.rename(os.path.join(dirpath, oldFilename), os.path.join(dirpath, newFilename))


def renameToBase(dirpath, oldFilename, newFilename):
    os.rename(os.path.join(dirpath, oldFilename), os.path.join(os.path.dirname(dirpath), newFilename))


def renameTemp(inpath):
    if not os.path.isdir(inpath):
        print('not found directory: ' + inpath)
        return
    for (dirpath, dirnames, filenames) in os.walk(inpath):
        for filename in filenames:
            renameInPlace(dirpath, filename, filename + renameTemp.temppostfix)
    return renameTemp.temppostfix


renameTemp.temppostfix = "temp"


def renameTempSingle(dirpath, filename):
    renameInPlace(dirpath, filename, filename + renameTemp.temppostfix)
    return renameTemp.temppostfix


def renameTempBack(dirpath, filename):
    newFilename = re.sub(renameTemp.temppostfix + '$', '', filename)
    renameInPlace(dirpath, filename, newFilename)


def concatPath(subpath) -> str:
    if not subpath == "": subpath = os.path.sep + subpath
    fullpath = os.getcwd() + subpath
    if not os.path.isdir(fullpath):
        print(fullpath, "is not a valid path")
    else:
        print(fullpath)
    return fullpath


def getNewName(name, dirCounter, fileCounter, digits=2) -> str:
    if name: name += "_"
    return name + ("%0" + str(digits) + "d_%02d") % (dirCounter, fileCounter) + ".jpg"


def removeIfEmtpy(dirpath):
    if not os.listdir(dirpath): os.rmdir(dirpath)


def writeToFile(path, content):
    ofile = open(path, 'w')
    ofile.write(content)
    ofile.close()


def moveToSubpath(filename, dirpath, subpath):
    os.makedirs(os.path.join(dirpath, subpath), exist_ok=True)
    if not isfile(dirpath, filename): return
    os.rename(os.path.join(dirpath, filename), os.path.join(dirpath, subpath, filename))


def getFileNamesOfMainDir(path):
    for (dirpath, dirnames, filenames) in os.walk(path):
        return [filename for filename in filenames if ".jpg" in filename]


def getFileNamesOfMainDir2(path, subpath=True) -> List[str]:
    out_filenames = []
    for (dirpath, dirnames, filenames) in os.walk(path):
        if not subpath and not dirpath == path: break
        out_filenames.extend([(dirpath, filename) for filename in filenames if ".jpg" in filename])
    out_filenames = natsorted(out_filenames, key=lambda x: x[1])
    return out_filenames


def isfile(*path) -> bool:
    return os.path.isfile(os.path.join(*path))


def file_has_ext(filename: str, file_extensions: Iterable, ignore_case=True) -> bool:
    for fileext in file_extensions:
        if ignore_case:
            fileext = fileext.lower()
            filename = filename.lower()
        if fileext == filename[filename.rfind("."):]:
            return True
    return False


def read_file_as_bytes(filepath: str) -> bytes:
    with open(filepath, "rb") as f:
        return f.read()


def modification_date(filename: str) -> datetime:
    t = os.path.getmtime(filename)
    return datetime.datetime.fromtimestamp(t)


def makedirs(*path) -> str:
    dirpath = os.path.join(*path)
    os.makedirs(dirpath, exist_ok=True)
    return dirpath


class Renamer:
    outstring = ""

    def __init__(self, write: bool, inpath: str):
        self.write = write
        self.inpath = inpath

    def rename(self, dirpath, filename, newFilename):
        if self.write:
            renameInPlace(dirpath, filename, newFilename)
        elif not filename == newFilename:
            self.outstring += filename + "\t" + newFilename + "\n"

    def close(self):
        if not self.write: writeToFile(self.inpath + "\\newNames.txt", self.outstring)
