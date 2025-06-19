#!/bin/bash

# This script is intended to be run via sudo by specific users.
# It safely flushes writes to disk and then drops the page cache.

sync
echo 3 > /proc/sys/vm/drop_caches
