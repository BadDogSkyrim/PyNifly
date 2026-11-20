#!/bin/sh
# Builds NiflyDLL for Linux (libNiflyDLL.so) and installs PyNifly with it into Blender's user add-ons, enabled.
# Run it again after pulling PyNifly or nifly. See LINUX.md.
set -e
here=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$here/../.." && pwd)
if [ ! -f "$repo/../Nifly/CMakeLists.txt" ] && [ ! -f "$here/../external/nifly/CMakeLists.txt" ]; then
    git clone --depth 1 https://github.com/BadDogSkyrim/nifly.git "$here/../external/nifly"
fi
cmake -S "$here" -B "$here/build" -DCMAKE_BUILD_TYPE=Release
cmake --build "$here/build" -j"$(nproc)"
cp "$here/build/libNiflyDLL.so" "$repo/io_scene_nifly/"
version=$(blender --version | sed -n 's/^Blender \([0-9]*\.[0-9]*\).*/\1/p' | head -1)
addons="$HOME/.config/blender/$version/scripts/addons"
mkdir -p "$addons"
rm -rf "$addons/io_scene_nifly"
cp -r "$repo/io_scene_nifly" "$addons/"
blender -b -noaudio --python-expr "import addon_utils, bpy; addon_utils.enable('io_scene_nifly', default_set=True, persistent=True); bpy.ops.wm.save_userpref()"
echo "PyNifly installed into Blender $version: $addons/io_scene_nifly"
