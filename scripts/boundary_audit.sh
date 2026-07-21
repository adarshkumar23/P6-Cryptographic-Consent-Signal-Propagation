#!/usr/bin/env bash
# Fails if core-side-patch/ pulls in signing dependencies that belong
# only to the satellite, or if app/ and core-side-patch/ cross-import.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FAIL=0

echo "== boundary audit: core-side-patch must not depend on satellite crypto internals =="

if grep -rn "^import nacl\|^from nacl" "$REPO_ROOT/core-side-patch" 2>/dev/null; then
  echo "FAIL: core-side-patch imports PyNaCl directly"
  FAIL=1
fi

if grep -rn "from app\.\|^import app\b" "$REPO_ROOT/core-side-patch" 2>/dev/null; then
  echo "FAIL: core-side-patch imports the satellite's app package"
  FAIL=1
fi

if grep -rEn "^\s*(import|from)\s+core_side_patch" "$REPO_ROOT/app" 2>/dev/null; then
  echo "FAIL: app/ (satellite) imports core-side-patch"
  FAIL=1
fi

echo "== boundary audit: satellite crypto.signing usage stays inside app/crypto and this repo's tests =="
if grep -rln "Ed25519PrivateKey" "$REPO_ROOT/core-side-patch" 2>/dev/null; then
  echo "FAIL: core-side-patch touches Ed25519 PRIVATE key material — core must never hold a private key"
  FAIL=1
fi

if [ "$FAIL" -eq 0 ]; then
  echo "PASS: boundary audit clean"
fi

exit $FAIL
