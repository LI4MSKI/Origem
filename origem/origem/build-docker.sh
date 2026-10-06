#!/usr/bin/env bash
# Origem bauen, ohne Arch installiert zu haben (Linux, macOS oder Windows mit WSL + Docker Desktop).
set -euo pipefail
cd "$(dirname "$0")"
docker run --rm --privileged -v "$PWD":/origem archlinux:latest bash -c '
  pacman -Syu --noconfirm archiso &&
  OUT=/origem/out /origem/build.sh
'
