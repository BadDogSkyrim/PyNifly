import os

from pynifly import *

if __name__ == "__main__":
    import codecs
    # import quickhull

    nifly_path = r"PyNifly\NiflyDLL\x64\Debug\NiflyDLL.dll"
    NifFile.Load(os.path.join(os.environ['PYNIFLY_DEV_ROOT'], nifly_path))

    i = 0
    walkroot = r"C:\Modding\Fallout4\mods\00 FO4 Assets\Meshes"
    with open('bgsm.csv', 'w') as outfile:
        print("Filepath,Shape,BGSM,", file=outfile)
        for root, dirlist, flist in os.walk(walkroot):
            if not r'\facegendata' in root.lower() \
               and not r'\precombined' in root.lower() \
               and not r'\architecture' in root.lower() \
               and not r'\interiors' in root.lower() \
               and not r'\landscape' in root.lower() \
               and not r'\scol' in root.lower():
                for f in filter(lambda x: x.lower().endswith('.nif'), flist):
                    fp = os.path.join(root, f)
                    n = NifFile(fp)
                    for s in n.shapes:
                        if s.shader_name:
                            print(fp[len(walkroot)+1:] + "," + s.name + "," + s.shader_name, file=outfile)
                    i += 1
