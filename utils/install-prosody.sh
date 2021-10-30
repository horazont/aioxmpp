#!/bin/bash -x
set -euo pipefail
sudo apt-get install prosody-$PROSODY_BRANCH
hg clone https://hg.prosody.im/prosody-modules/ prosody-modules
sudo cp -vr utils/prosody-cfg/$PROSODY_BRANCH/* /etc/prosody/
modules_dir="$(pwd)/prosody-modules"
pushd /etc/prosody
sudo mkdir plugins
# these scripts come from the config directory
sudo bash -xeuo pipefail ./patch.sh "$modules_dir"
sudo bash -xeuo pipefail ./link.sh "$modules_dir"
sudo chown -R $(id -u):$(id -g) /etc/prosody
sudo ls -alR /etc/prosody || true
