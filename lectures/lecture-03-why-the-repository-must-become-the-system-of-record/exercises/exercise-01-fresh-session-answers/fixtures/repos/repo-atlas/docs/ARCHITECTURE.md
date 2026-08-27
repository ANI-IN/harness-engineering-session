# Architecture

Two layers: renderer (tile math, pure) and cache (disk layout under tiles/).

Hard rule: renderer never reads the filesystem.
