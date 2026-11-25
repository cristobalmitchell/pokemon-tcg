
<center>
  <img src="dataset-cover-image.png" />
</center>

# The Complete Pokémon TCG Dataset

Every **English Pokémon Trading Card Game card**, from Base Set (January 1999) to Delta Reign (November 2026): **20,776 cards in 177 sets**, with 28,412 attacks, 4,157 abilities and 188 theme decks, as relational CSV tables and one SQLite database.

It's the companion to **[The Complete Pokédex Dataset](https://github.com/cristobalmitchell/pokedex)**. `card_pokemon.csv` links each card to the National Pokédex numbers of the Pokémon on it, so card HP and attacks can be joined to game stats, types, forms and learnsets.

## Files

| File | Rows | One row per |
|---|---|---|
| `data/cards.csv` | 20,776 | card: supertype, subtypes, HP, types, evolution, weakness, resistance, retreat cost, rarity, artist, regulation mark, legality, image links |
| `data/card_attacks.csv` | 28,412 | attack: energy cost, damage as printed (`30+`) and as a number with its modifier, effect text |
| `data/card_abilities.csv` | 4,157 | Ability, Poké-Power, Poké-Body or Pokémon Power |
| `data/card_pokemon.csv` | 17,654 | (card, National Pokédex number) |
| `data/sets.csv` | 177 | set: series, size, release date, legality, symbol and logo links |
| `data/decks.csv` | 188 | theme deck |
| `data/deck_cards.csv` | 3,976 | card line in a theme deck |
| `data/tcg.sqlite` | | every table, with primary and foreign keys |

The data dictionary, with a description of every column, is in [`dataset-metadata.json`](dataset-metadata.json).

```
sets (set_id) ─< cards (card_id) ─┬─< card_attacks
                                  ├─< card_abilities
                                  └─< card_pokemon (national_number) >── Pokédex dataset: pokemon_utf8.csv
decks (deck_id) ─< deck_cards (card_id) >── cards
```

## Build
```bash
git clone --depth 1 https://github.com/PokemonTCG/pokemon-tcg-data.git .cache/pokemon-tcg-data
python scripts/build.py .cache/pokemon-tcg-data   # data/*.csv and data/tcg.sqlite
python scripts/build_metadata.py                  # dataset-metadata.json for Kaggle
python scripts/validate.py                        # integrity checks; run before every upload
python scripts/build_cover.py                     # dataset-cover-image.png (needs Pillow and matplotlib)
python scripts/stage_kaggle.py                    # kaggle_upload/: files and guide for Kaggle's web uploader
```

To publish on Kaggle, follow `kaggle_upload/UPLOAD.md`. It lists the files to drag in, the title, subtitle, license, tags and cover, and how to add the starter notebook. `kaggle_upload/COLUMNS.md` has every column description ready to paste into the Data Card.

`validate.py` checks:
- **Keys:** unique ids and every foreign key.
- **Counts:** set sizes and attack counts agree with the other tables.
- **Valid values:** every type and Energy symbol, and the converted Energy cost against the cost symbols.
- **HP:** every Pokémon card has HP and no Energy card does. Trainer cards played as Pokémon, such as Fossils and Clefairy Doll, may have it.
- **Pokédex numbers:** all are between 1 and 1025.
- **Metadata:** it documents every column, in order.

## Starter notebook
[`notebooks/pokemon_tcg_eda.ipynb`](notebooks/pokemon_tcg_eda.ipynb) is an executed first analysis. It covers:
- cards released per year
- power creep (median HP doubled and median damage per Energy tripled, 1999–2026)
- the rise of rule-box cards
- card HP against each species' HP stat in the games (Spearman ρ = 0.75, via the Pokédex dataset)
- the most prolific illustrators

## Notes
- Read `cards.csv` with `pd.read_csv(..., low_memory=False)`. A few columns, such as `level` ("X" vs "12"), mix numbers and text, and pandas otherwise warns about mixed types.
- Multi-valued cells (types, subtypes, energy costs) are separated by `|`.
- Legality is the snapshot's (Standard rotation through regulation mark J).
- Image links point at the source's image host and may stop working after the source's API goes offline on March 1, 2027.
- There are no prices. Price feeds are commercial.

## Licenses
- **Code** (`scripts/`, `notebooks/`): MIT; see [`LICENSE`](LICENSE).
- **Dataset** (`data/`): custom non-commercial terms, which is the "Other" option on Kaggle. Use is limited to non-commercial research, education and analysis, and must credit both this dataset and PokemonTCG/pokemon-tcg-data. The author's own contributions (table design, derived columns, corrections, documentation, cover) are reusable under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). See [`DATA_LICENSE.md`](DATA_LICENSE.md).
- **Why not a standard license?** Card names, text and images belong to The Pokémon Company, and the upstream compilation publishes no license, so a standard license would claim rights this project doesn't hold.
- **No affiliation:** not affiliated with or endorsed by Nintendo, The Pokémon Company, Creatures Inc., GAME FREAK inc. or the PokemonTCG project. To request removal of material you hold rights in, [open an issue](https://github.com/cristobalmitchell/pokemon-tcg/issues).

## Source and credits
- **Source:** [PokemonTCG/pokemon-tcg-data](https://github.com/PokemonTCG/pokemon-tcg-data) (English cards, v2 JSON). That project is now kept for historical use only, and this dataset is a snapshot taken in November 2026.
- **Rights:** card names, card text and card images are © 1995–2026 Nintendo, Creatures Inc. and GAME FREAK inc.
