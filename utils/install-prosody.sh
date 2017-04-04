#!/bin/bash
pip install hererocks
hererocks lua_install -r^ --lua=5.1
luarocks install luaexpat
luarocks install luafilesystem
luarocks install luasocket
luarocks install luasec
hg clone https://hg.prosody.im/$PROSODY_BRANCH/ prosody
cd prosody
./configure "--with-lua=$(pwd)/../lua_install"
make

