#!/bin/bash -x
set -euo pipefail
lua_version=${LUA_VERSION:-5.1}
if [ "x${WITH_BUILD_DEP:-no}" = 'xyes' ]; then
    sudo apt build-dep prosody
fi
pip install hererocks
hererocks lua_install -r^ --lua=$lua_version
luarocks install luaexpat
luarocks install luafilesystem
luarocks install luasocket
luarocks install luasec
luarocks install luabitop
hg clone https://hg.prosody.im/$PROSODY_BRANCH/ prosody
hg clone https://hg.prosody.im/prosody-modules/ prosody-modules
cp -r utils/prosody-cfg/$PROSODY_BRANCH/* prosody/
cd prosody
./configure "--with-lua=$(pwd)/../lua_install"
make
# these scripts come from the config directory
bash -xeuo pipefail ./patch.sh
bash -xeuo pipefail ./link.sh
