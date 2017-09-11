#!/bin/bash -x
set -euo pipefail
pip install hererocks
hererocks lua_install -r^ --lua=5.1
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
