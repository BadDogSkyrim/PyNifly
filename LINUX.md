# PyNifly on Linux

PyNifly's native library, NiflyDLL, builds on Linux as `libNiflyDLL.so` from the same sources the Visual Studio project
compiles. The add-on loads it in place of `NiflyDLL.dll`; on Windows nothing changes.

## Build and install

Needs Blender (4.0 or later), CMake (3.16 or later), GCC (C++20) and git.

```bash
git clone https://github.com/BadDogSkyrim/PyNifly.git
PyNifly/NiflyDLL/linux/install-blender.sh
```

The script builds `libNiflyDLL.so` in `NiflyDLL/linux/build`, copies the add-on with it into Blender's user add-ons
(`~/.config/blender/<version>/scripts/addons/io_scene_nifly`) and enables it. Run it again after pulling updates.

nifly ([BadDogSkyrim/nifly](https://github.com/BadDogSkyrim/nifly)) is taken from where the Visual Studio project expects
it, a folder `Nifly` beside the PyNifly checkout; without one, the script clones it into `NiflyDLL/external/nifly`.
`cmake -DNIFLY_DIR=<path>` names another.

## How it differs from the Windows build

- `NiflyDLL/linux/compat/windows.h` answers the one Windows call NiflyDLL makes (the path of its own library, for
  `FindProjectRoot`) through `dladdr`, and `compat/prelude.h` drops MSVC's `__declspec`.
- Nothing else in the C++ sources changes but the letter case of a few `#include`s, which Linux's file systems read
  exactly.
- Developer mode (`PYNIFLY_DEV_ROOT`) still looks for the Windows Debug build; on Linux install the add-on with the
  script.

- The test suites name their fixtures as Windows paths (`r"tests\SkyrimSE\..."`), which Linux reads as one file name:
  they do not run on Linux as they are.
