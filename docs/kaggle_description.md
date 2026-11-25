# The Complete Pokémon TCG Dataset

**44,778 Pokémon cards** as relational tables and an SQLite database:
- **The international Trading Card Game:** every card from Base Set (1999) to Delta Reign (November 2026).
- **Pokémon TCG Pocket:** every card through October 2026, with pack pull rates.
- **Japanese and other Asian sets:** 18,660 cards.

Around the cards:
- **Text:** 54,868 attacks, and card names in 14 languages.
- **Variants:** printed variants with their TCGplayer, Cardmarket and CardTrader ids.
- **Prices:** 488,808 monthly TCGplayer sale prices from 2022 to 2024.

It links to **[The Complete Pokédex Dataset](https://www.kaggle.com/datasets/cristobalmitchell/pokedex)** by National Pokédex number.

## What's inside

| File | Rows | One row per |
|---|---|---|
| `cards.csv` | 44,778 | card: region, game, stage, HP, types, evolution, weakness, retreat cost, rarity, artist, regulation mark, legality, image link |
| `card_names.csv` | 167,307 | card name in up to 14 languages |
| `card_attacks.csv` | 54,868 | attack: Energy cost, damage as printed and as a number, effect text |
| `card_abilities.csv` | 8,063 | Ability, Poké-Power, Poké-Body or Ancient Trait |
| `card_pokemon.csv` | 33,507 | (card, National Pokédex number) link to the Pokédex dataset |
| `card_variants.csv` | 47,807 | printed variant (reverse holo, 1st edition, stamps) and its marketplace ids |
| `price_history.csv` | 488,808 | (card, finish, condition, month): TCGplayer sale prices and number of sales |
| `id_crosswalk.csv` | 33,230 | TCGdex id ↔ pokemontcg.io ↔ TCGplayer ↔ Cardmarket ↔ CardTrader |
| `pocket_pull_rates.csv` | 1,145 | Pocket pull rate per set, pack, slot and rarity |
| `card_boosters.csv` | 4,786 | booster pack a card can be pulled from |
| `sets.csv` / `set_names.csv` | 582 / 1,911 | set: series, region, game, size, release date, legality, marketplace ids |
| `decks.csv` / `deck_cards.csv` | 188 / 3,976 | theme deck and its card list |
| `tcg.sqlite` | | every table, with keys |

## Quick start

```python
import pandas as pd
cards = pd.read_csv('/kaggle/input/pokemon-tcg/cards.csv', low_memory=False)
attacks = pd.read_csv('/kaggle/input/pokemon-tcg/card_attacks.csv')
tcg = cards[(cards.region == 'international') & (cards.game == 'tcg')]

# Damage per Energy across eras: how much has power crept?
a = attacks.merge(tcg[['card_id', 'release_date']], on='card_id')
a = a[a.converted_energy_cost > 0]
(a.base_damage / a.converted_energy_cost).groupby(a.release_date.str[:4]).median()
```

What did the most valuable cards sell for?

```python
prices = pd.read_csv('/kaggle/input/pokemon-tcg/price_history.csv')
nm = prices[(prices.condition == 'nearmint') & (prices.month == '2024-08')]
nm.merge(cards[['card_id', 'name', 'set_name', 'rarity']], on='card_id').nlargest(10, 'avg_price_usd')
```

Join it to the Pokédex dataset to compare a Pokémon's card HP with its game stats:

```python
pokedex = pd.read_csv('/kaggle/input/pokedex/pokemon_utf8.csv')
links = pd.read_csv('/kaggle/input/pokemon-tcg/card_pokemon.csv')
hp = links.merge(tcg[['card_id', 'hp']], on='card_id').merge(pokedex, on='national_number')
```

**Starter notebook:** the dataset's starter analysis covers power creep, the rise of rule-box cards, card HP against game stats, the most prolific illustrators, prices by rarity and the Pocket rarity ladder. Fork it as a starting point.

## Ideas
- **Power creep:** HP and damage per Energy by year and series.
- **Prices:** what makes a card valuable: rarity, artist, the Pokémon's popularity (join Smogon usage from the Pokédex dataset), set age.
- **Rarity:** how the rarity ladder changed (Rare Holo → Illustration Rare → Special Illustration Rare), and Pocket's pull odds.
- **Japan vs. the West:** compare a Japanese set with its English release; translation with `card_names.csv`.
- **Card game vs. video game:** card HP and attack damage against base stats from the Pokédex dataset.
- **NLP:** attack, ability and Trainer text, flavor text.

## Notes
- `region` is `international` or `asia`; `game` is `tcg` or `pocket`. Filter on both for like-for-like comparisons.
- `text_language` is the language of a card's name and text: English for international cards, the card's own language for Asian cards.
- The newest 12 Pocket sets come from the Pokémon TCG Pocket database and have no attack text (`attack_count` is blank).
- Prices are historical: TCGplayer sales recorded from November 2022 to September 2024, aggregated by month, in US dollars.
- `ptcgio_id` and `id_crosswalk.csv` map 99.5% of pokemontcg.io cards, for projects moving off that API, which goes offline on March 1, 2027.
- Multi-valued cells (types, Energy costs, stamps) are separated by `|`.

## License
**Other (non-commercial, attribution required).** The card names, card text and card images belong to The Pokémon Company, so no standard license fits.
- **You may:** use the data for non-commercial research, education, analysis and notebooks.
- **You must:** credit *"The Complete Pokémon TCG Dataset by Cristobal Mitchell"* and *"card data from TCGdex"*, and keep `THIRD_PARTY_NOTICES.md` (included) with copies.
- **You may not:** sell the data or use it in a commercial product.
- **The author's own contributions:** the table design, ID crosswalk, derived columns, corrections, documentation and cover are © 2026 Cristobal Mitchell and reusable under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). The build and analysis code on GitHub is MIT-licensed.
- **No affiliation:** not affiliated with or endorsed by Nintendo, The Pokémon Company, Creatures Inc., GAME FREAK inc., TCGdex, TCGplayer or the PokemonTCG project.

The full terms are in the repository's `DATA_LICENSE.md`.

## Sources and credits
- **Cards, sets, variants, marketplace ids and images:** [TCGdex](https://github.com/tcgdex/cards-database) (MIT).
- **Price history:** [TCGdex price-history](https://github.com/tcgdex/price-history) (MIT), from TCGplayer.
- **Pocket pull rates and newest sets:** [Pokémon TCG Pocket database](https://github.com/flibustier/pokemon-tcg-pocket-database) (MIT).
- **pokemontcg.io ids and theme decks:** [PokemonTCG/pokemon-tcg-data](https://github.com/PokemonTCG/pokemon-tcg-data).
- **Rights:** card names, card text and card images are © 1995–2026 Nintendo, Creatures Inc. and GAME FREAK inc.

The build is reproducible: `scripts/build.py` builds the tables and `scripts/validate.py` checks them. Both are on [GitHub](https://github.com/cristobalmitchell/pokemon-tcg).

**Companion dataset:** [The Complete Pokédex Dataset](https://www.kaggle.com/datasets/cristobalmitchell/pokedex) has every Pokémon's game data, forms, moves, Smogon usage, artwork and cries.
