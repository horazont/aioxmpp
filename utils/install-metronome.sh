#!/bin/bash -x
set -euo pipefail
if [ "x${WITH_BUILD_DEP:-no}" = 'xyes' ]; then
    sudo apt-get build-dep prosody
fi
pip install hererocks
hererocks lua_install -r^ --lua=5.1
luarocks install luaexpat
luarocks install luafilesystem
luarocks install luasocket
luarocks install luasec
luarocks install luabitop
luarocks install luaevent
git clone https://github.com/maranda/metronome metronome --branch "$METRONOME_VERSION"
cp -r utils/metronome-cfg/$METRONOME_VERSION/* metronome/
cd metronome
./configure "--with-lua=$(pwd)/../lua_install"
make
