#!/bin/bash -x
set -euo pipefail
pip install hererocks
hererocks lua_install -r^ --lua=5.1
luarocks install luaexpat
luarocks install luafilesystem
luarocks install luasocket
luarocks install luasec
hg clone https://hg.prosody.im/$PROSODY_BRANCH/ prosody
hg clone https://hg.prosody.im/prosody-modules/ prosody-modules
# this tarball provides configuration, patches and certificates for the prosody
curl https://sotecware.net/files/noindex/prosody-cfg-$PROSODY_BRANCH.tar.gz | tar -vxz
cd prosody
./configure "--with-lua=$(pwd)/../lua_install"
make
# these scripts come from the config tarball
bash -xeuo pipefail ./patch.sh
bash -xeuo pipefail ./link.sh
