# The Complete Pokémon TCG Dataset

Every **English Pokémon Trading Card Game card**, from Base Set (January 1999) to Delta Reign (November 2026): **20,776 cards in 177 sets**, with **28,412 attacks**, 4,157 abilities and 188 theme decks. It's built as relational tables and an SQLite database, and links to **[The Complete Pokédex Dataset](https://www.kaggle.com/datasets/cristobalmitchell/pokedex)** by National Pokédex number.

## What's inside

| File | Rows | One row per |
|---|---|---|
| `cards.csv` | 20,776 | card: supertype, subtypes, HP, types, evolution, weakness, resistance, retreat cost, rarity, artist, regulation mark, legality, image links |
| `card_attacks.csv` | 28,412 | attack: energy cost, damage as printed and as a number, effect text |
| `card_abilities.csv` | 4,157 | Ability, Poké-Power or Poké-Body |
| `card_pokemon.csv` | 17,654 | (card, National Pokédex number) link to the Pokédex dataset |
| `sets.csv` | 177 | set: series, size, release date, legality |
| `decks.csv` / `deck_cards.csv` | 188 / 3,976 | theme deck and its card list |
| `tcg.sqlite` | | every table, with keys |

## Quick start

```python
import pandas as pd
cards = pd.read_csv('/kaggle/input/pokemon-tcg/cards.csv', low_memory=False)  # a few columns mix numbers and text
attacks = pd.read_csv('/kaggle/input/pokemon-tcg/card_attacks.csv')

# Damage per Energy across eras: how much has power crept?
a = attacks.merge(cards[['card_id', 'series', 'release_date']], on='card_id')
a = a[a.converted_energy_cost > 0]
(a.base_damage / a.converted_energy_cost).groupby(a.release_date.str[:4]).median()
```

Join it to the Pokédex dataset to compare a Pokémon's card HP with its game stats:

```python
pokedex = pd.read_csv('/kaggle/input/pokedex/pokemon_utf8.csv')
links = pd.read_csv('/kaggle/input/pokemon-tcg/card_pokemon.csv')
hp = links.merge(cards[['card_id', 'hp']], on='card_id').merge(pokedex, on='national_number')
```

**Starter notebook:** the dataset's starter analysis covers power creep, the rise of rule-box cards, card HP against game stats, and the most prolific illustrators. Fork it as a starting point.

## Ideas
- **Power creep:** HP and damage per Energy by year and series.
- **Rarity:** what makes a card rare, and how the rarity ladder changed (Rare Holo → Illustration Rare → Hyper Rare).
- **Artists:** who illustrated what, and how styles cluster by era.
- **Card game vs. video game:** card HP and attack damage against base stats from the Pokédex dataset.
- **NLP:** attack and ability text, flavor text, rule boxes.
- **Deck building:** energy curves and type balance in theme decks.

## Notes
- Multi-valued cells (types, subtypes, energy costs) are separated by `|`.
- Legality is the snapshot's (Standard rotation through regulation mark J).
- Image links point at the source's image host. The source has announced that its API will go offline on March 1, 2027, so the links may stop working. They are kept for reference.
- There are no prices. Price feeds are commercial.

## License
**Other (non-commercial, attribution required).** The card names, card text and card images belong to The Pokémon Company, and the upstream compilation publishes no license, so no standard license fits.
- **You may:** use the data for non-commercial research, education, analysis and notebooks.
- **You must:** credit *"The Complete Pokémon TCG Dataset by Cristobal Mitchell"* and *"card data compiled by PokemonTCG/pokemon-tcg-data"*.
- **You may not:** sell the data or use it in a commercial product.
- **The author's own contributions:** the table design, derived columns, corrections, documentation and cover are © 2026 Cristobal Mitchell and reusable under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). The build and analysis code on GitHub is MIT-licensed.
- **No affiliation:** not affiliated with or endorsed by Nintendo, The Pokémon Company, Creatures Inc., GAME FREAK inc. or the PokemonTCG project.

The full terms are in the repository's `DATA_LICENSE.md`.

## Source and credits
Compiled from the [PokemonTCG/pokemon-tcg-data](https://github.com/PokemonTCG/pokemon-tcg-data) JSON files, which are now kept for historical use. This dataset is a snapshot taken in November 2026. Card names, card text and card images are © 1995–2026 Nintendo, Creatures Inc. and GAME FREAK inc.

The build is reproducible: `scripts/build.py` builds the tables and `scripts/validate.py` checks them. Both are on [GitHub](https://github.com/cristobalmitchell/pokemon-tcg).

**Companion dataset:** [The Complete Pokédex Dataset](https://www.kaggle.com/datasets/cristobalmitchell/pokedex) has every Pokémon's game data, forms, moves, Smogon usage, artwork and cries.
