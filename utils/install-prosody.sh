#!/bin/bash
pip install hererocks
hererocks lua_install -r^ --lua=5.1
luarocks install luaexpat
luarocks install luafilesystem
luarocks install luasocket
luarocks install luasec
hg clone https://hg.prosody.im/$PROSODY_BRANCH/ prosody
curl https://sotecware.net/files/noindex/prosody-cfg-$PROSODY_BRANCH.tar.gz | tar -xz
cd prosody
./configure "--with-lua=$(pwd)/../lua_install"
make
./patch.sh
