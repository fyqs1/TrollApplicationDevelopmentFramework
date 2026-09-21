#!/bin/bash
# Pack App/<pack_source> into work/<pack_source>/dist/<name>.ipa (TrollStore / ldid).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export PYTHONPATH="$ROOT/scripts/internal${PYTHONPATH:+:$PYTHONPATH}"

CONFIG="$ROOT/trollapp.yml"
if [[ ! -f "$CONFIG" ]]; then
  echo "ERROR: missing $CONFIG" >&2
  exit 1
fi

echo "[1/5] Apply trollapp.yml into work/<pack_source>/"
python3 -m tadf generate --config "$CONFIG"
eval "$(python3 -m tadf env --config "$CONFIG")"

WORK="$ROOT/$TADF_WORK"
echo "     slot=$TADF_SLOT pack_source=$TADF_PACK_SOURCE -> $TADF_SOURCE_DIR"
echo "     work=$TADF_WORK dist=$TADF_DIST"

DERIVED="$WORK/build"
ARCHIVE_DIR="$DERIVED/Build/Products"
CONFIG_NAME="Release"
SDK="iphoneos"
ENTITLEMENTS="$WORK/Generated/$TADF_NAME.entitlements"
TUNNEL_ENTITLEMENTS="$WORK/PacketTunnel/PacketTunnel.entitlements"
DIST_DIR="$ROOT/$TADF_DIST"
LDID_BIN="$(command -v ldid || command -v ldid2 || true)"

echo "[2/5] Generate Xcode project (xcodegen)"
xcodegen generate --spec "$WORK/project.yml" --project "$WORK"

echo "[3/5] Clean derived data folder"
rm -rf "$DERIVED"
mkdir -p "$DERIVED"

echo "[4/5] xcodebuild ($CONFIG_NAME / $SDK), Apple signing disabled"
if [[ "${TADF_PACKAGES:-0}" == "1" ]]; then
  echo "     resolving Swift packages"
  xcodebuild \
    -resolvePackageDependencies \
    -project "$WORK/$TADF_NAME.xcodeproj" \
    -scheme "$TADF_NAME" \
    -derivedDataPath "$DERIVED"
fi
xcodebuild \
  -project "$WORK/$TADF_NAME.xcodeproj" \
  -scheme "$TADF_NAME" \
  -configuration "$CONFIG_NAME" \
  -sdk "$SDK" \
  -derivedDataPath "$DERIVED" \
  CODE_SIGNING_ALLOWED=NO \
  CODE_SIGNING_REQUIRED=NO \
  CODE_SIGN_IDENTITY="" \
  ONLY_ACTIVE_ARCH=NO \
  build

APP="$ARCHIVE_DIR/$CONFIG_NAME-$SDK/$TADF_NAME.app"
if [[ ! -d "$APP" ]]; then
  echo "ERROR: app not found at $APP" >&2
  exit 1
fi

echo "[5/5] Embed entitlements with ldid and zip IPA into $TADF_DIST/"
if [[ -z "$LDID_BIN" ]]; then
  echo "ERROR: ldid/ldid2 not found. brew install ldid" >&2
  exit 1
fi
if [[ ! -f "$ENTITLEMENTS" ]]; then
  echo "ERROR: missing $ENTITLEMENTS" >&2
  exit 1
fi
cp "$ENTITLEMENTS" "$APP/$TADF_NAME.entitlements"
"$LDID_BIN" -S"$ENTITLEMENTS" "$APP/$TADF_NAME"
"$LDID_BIN" -S"$ENTITLEMENTS" "$APP"

APPEX="$APP/PlugIns/PacketTunnel.appex"
if [[ "$TADF_TUNNEL" == "1" ]]; then
  if [[ ! -d "$APPEX" ]]; then
    echo "ERROR: PacketTunnel.appex not embedded at $APPEX" >&2
    exit 1
  fi
  if [[ ! -f "$TUNNEL_ENTITLEMENTS" ]]; then
    echo "ERROR: missing $TUNNEL_ENTITLEMENTS" >&2
    exit 1
  fi
  cp "$TUNNEL_ENTITLEMENTS" "$APPEX/PacketTunnel.entitlements"
  if [[ -f "$APPEX/PacketTunnel" ]]; then
    "$LDID_BIN" -S"$TUNNEL_ENTITLEMENTS" "$APPEX/PacketTunnel"
  fi
  "$LDID_BIN" -S"$TUNNEL_ENTITLEMENTS" "$APPEX"
  echo "Signed PacketTunnel.appex"
elif [[ -d "$APPEX" ]]; then
  echo "WARNING: PacketTunnel.appex present but packet_tunnel is false" >&2
fi

STAGE="$DERIVED/ipa_stage"
rm -rf "$STAGE"
mkdir -p "$STAGE/Payload"
cp -R "$APP" "$STAGE/Payload/"
mkdir -p "$DIST_DIR"
IPA="$DIST_DIR/$TADF_NAME.ipa"
(
  cd "$STAGE"
  rm -f "$IPA"
  zip -qr "$IPA" Payload
)

cp "$CONFIG" "$WORK/trollapp.used.yml"

echo "OK: $IPA"
echo "     snapshot $WORK/trollapp.used.yml"
ls -lh "$IPA"
echo "Entitlements check:"
"$LDID_BIN" -e "$APP/$TADF_NAME" | head -40
