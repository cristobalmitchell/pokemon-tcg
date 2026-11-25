#!/usr/bin/env bash
# Download the sources of The Complete Pokémon TCG Dataset (about 560 MB) into .cache/ or the given folder.
#
#   bash scripts/fetch_sources.sh            # then: python scripts/build.py .cache
#
# Running it again updates the clones in place.
set -euo pipefail
CACHE=${1:-"$(dirname "$0")/../.cache"}
mkdir -p "$CACHE"
cd "$CACHE"

# clone URL DIR [PATHS...]: shallow clone; with PATHS, check out only those folders
clone() {
  local url=$1 dir=$2
  shift 2
  if [ -d "$dir/.git" ]; then
    git -C "$dir" pull -q --ff-only
  elif [ $# -gt 0 ]; then
    git clone -q --depth 1 --filter=blob:none --sparse "$url" "$dir"
    git -C "$dir" sparse-checkout set "$@"
  else
    git clone -q --depth 1 "$url" "$dir"
  fi
  echo "$dir: $(git -C "$dir" log -1 --format='%h %cs')"
}

clone https://github.com/tcgdex/cards-database.git cards-database data data-asia meta
clone https://github.com/tcgdex/price-history.git price-history en meta
clone https://github.com/flibustier/pokemon-tcg-pocket-database.git pokemon-tcg-pocket-database dist
clone https://github.com/PokemonTCG/pokemon-tcg-data.git pokemon-tcg-data
curl -sSfL -o datas.json https://assets.tcgdex.net/datas.json   # index of the card images that exist
echo "datas.json: $(wc -c < datas.json) bytes"
