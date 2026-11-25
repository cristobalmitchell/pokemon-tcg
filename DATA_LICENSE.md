# Data terms

The Complete Pokémon TCG Dataset (`data/`) is published under custom terms. On Kaggle this is the license
option "Other (specified in description)". No standard license fits, because most of the content is not the
author's to license:
- **Card content:** card names, card text, set names and the linked card images are © The Pokémon Company,
  Nintendo, Creatures Inc. and GAME FREAK inc.
- **Upstream compilations:** the card data comes from open-source projects. Their licenses and copyright
  notices are in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md):
  - [TCGdex](https://github.com/tcgdex/cards-database) (MIT): cards, sets, variants and marketplace ids.
  - [TCGdex price-history](https://github.com/tcgdex/price-history) (MIT): TCGplayer sales 2022–2024.
  - [Pokémon TCG Pocket database](https://github.com/flibustier/pokemon-tcg-pocket-database) (MIT): Pocket
    packs and pull rates, and the newest Pocket sets.
  - [PokemonTCG/pokemon-tcg-data](https://github.com/PokemonTCG/pokemon-tcg-data) (no published license):
    only the pokemontcg.io ids and the theme decks.

## You may
- Use the dataset for **non-commercial research, education, analysis and personal projects**, including
  Kaggle notebooks and derived analyses.

## You must
- **Credit the dataset and its main source:** *"The Complete Pokémon TCG Dataset by Cristobal Mitchell"* (with
  a link to https://www.kaggle.com/datasets/cristobalmitchell/pokemon-tcg or
  https://github.com/cristobalmitchell/pokemon-tcg) and *"card data from TCGdex"*.
- **Keep the notices:** when you redistribute the data, include `THIRD_PARTY_NOTICES.md`.
- **Keep it non-commercial:** do not sell the data or use it in a commercial product.

## The author's own contributions
The relational table design, the ID crosswalk, the derived columns (for example `base_damage`,
`damage_modifier`, `primary_type`, `evolves_to`, `text_language` and the monthly price aggregates), the
corrections, the documentation and the cover image are © 2026 Cristobal Mitchell. They may be reused under
[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). The build and analysis code is MIT
(see [`LICENSE`](LICENSE)).

## Pokémon intellectual property
Pokémon and all Pokémon character names, card names, card text and artwork are © 1995–2026 Nintendo,
Creatures Inc. and GAME FREAK inc. Pokémon and Pokémon character names are trademarks of Nintendo. This
project is not affiliated with, endorsed by or sponsored by Nintendo, The Pokémon Company, Creatures Inc.,
GAME FREAK inc., TCGdex, TCGplayer or the PokemonTCG project.

## Removal requests
If you hold rights in any material here and want it removed, open an issue at
https://github.com/cristobalmitchell/pokemon-tcg/issues and it will be taken down.
