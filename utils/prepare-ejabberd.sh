#!/bin/bash -x
set -euo pipefail
docker pull ejabberd/ecs:$EJABBERD_VERSION
