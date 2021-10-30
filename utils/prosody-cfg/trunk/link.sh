#!/bin/bash
modules_dir="$1"
ln -s "$modules_dir/mod_storage_memory" plugins/
ln -s "$modules_dir/mod_http_upload" plugins/
