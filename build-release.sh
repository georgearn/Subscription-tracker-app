#!/usr/bin/env bash
# Build the Android RELEASE APK (signed with the real key), via the same
# kivy/buildozer Docker setup as build.sh. See build.sh for the reasoning
# behind the persistent volumes and --entrypoint bash workaround.
#
# Signing key lives outside the repo at ~/.android-keystores/android-release.jks
# (shared across apps signed with the same identity - see that folder's
# README.md). It's bind-mounted read-only into the container and referenced
# via the P4A_RELEASE_* env vars that python-for-android's build step picks
# up automatically to sign + zipalign the APK.
#
# Run from the project root, in Git Bash (MSYS), with Docker Desktop running.
# If buildozer prompts about running as root, pipe confirmation in:
#   echo y | ./build-release.sh

set -e

KEYSTORE_DIR="$HOME/.android-keystores"
KEYSTORE_FILE="android-release.jks"
KEYSTORE_ALIAS="androidrelease"

if [ ! -f "$KEYSTORE_DIR/$KEYSTORE_FILE" ]; then
    echo "Keystore not found at $KEYSTORE_DIR/$KEYSTORE_FILE" >&2
    exit 1
fi

# Password is env-var driven so it's never hardcoded in the repo.
# Set it first: . "$HOME/.android-keystores/set-env.ps1" is PowerShell-only,
# so for this bash script export it directly:
#   export KEYSTORE_PASSWORD="..."
if [ -z "$KEYSTORE_PASSWORD" ]; then
    echo "Set KEYSTORE_PASSWORD env var first (see ~/.android-keystores/set-env.ps1 for the value)." >&2
    exit 1
fi

docker volume create subscr_buildozer_home >/dev/null
docker volume create subscr_android_home >/dev/null
docker volume create subscr_gradle_home >/dev/null

MSYS_NO_PATHCONV=1 docker run --rm -i -v "$(pwd)":/home/user/hostcwd \
    -v "$KEYSTORE_DIR":/keystore:ro \
    -v subscr_buildozer_home:/home/user/.buildozer \
    -v subscr_android_home:/root/.android \
    -v subscr_gradle_home:/root/.gradle \
    -e P4A_RELEASE_KEYSTORE="/keystore/$KEYSTORE_FILE" \
    -e P4A_RELEASE_KEYSTORE_PASSWD="$KEYSTORE_PASSWORD" \
    -e P4A_RELEASE_KEYALIAS="$KEYSTORE_ALIAS" \
    -e P4A_RELEASE_KEYALIAS_PASSWD="$KEYSTORE_PASSWORD" \
    --entrypoint bash kivy/buildozer -c \
    "export HOME=/home/user && cd /home/user/hostcwd && /home/user/.venv/bin/buildozer android release"

echo
echo "Release APK (if successful) is in bin/, signed with alias '$KEYSTORE_ALIAS'."
