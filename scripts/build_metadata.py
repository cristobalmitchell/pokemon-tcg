"""Write dataset-metadata.json (Kaggle) with a description of every column of every CSV.

Usage:
    python scripts/build_metadata.py
"""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
I, N, S = 'integer', 'number', 'string'
MULTI = ' Several values are separated by "|".'

COMMON = {
    'card_id': ('Card id: <set_id>-<number> (e.g. "sv3pt5-25"). Joins to cards.csv.', S),
    'set_id': ('Set id (e.g. "base1", "sv10", "me6"). Joins to sets.csv.', S),
    'deck_id': ('Theme deck id. Joins to decks.csv.', S),
    'national_number': ('National Pokédex number. Joins to The Complete Pokédex Dataset (pokemon_utf8.csv).', I),
}
DOCS = {
    'sets.csv': {
        'name': ('Set name (e.g. "Base", "Delta Reign").', S),
        'series': ('Series / era (e.g. "Base", "Sword & Shield", "Scarlet & Violet", "Mega Evolution").', S),
        'printed_total': ('Number printed on the cards as the set size (excludes secret rares).', I),
        'total': ('Total cards in the set, including secret rares.', I),
        'card_count': ('Cards of the set in cards.csv.', I),
        'ptcgo_code': ('Set code used by Pokémon TCG Online / Live (e.g. "DLR").', S),
        'release_date': ('Release date (YYYY-MM-DD).', S),
        'updated_at': ('When the source last updated the set.', S),
        'legal_standard': ('Legal in the Standard format at the time of the snapshot (Legal / blank).', S),
        'legal_expanded': ('Legal in the Expanded format.', S),
        'legal_unlimited': ('Legal in the Unlimited format.', S),
        'symbol_url': ('URL of the set symbol image.', S),
        'logo_url': ('URL of the set logo image.', S),
    },
    'cards.csv': {
        'set_name': ('Set name.', S),
        'series': ('Series / era of the set.', S),
        'release_date': ('Release date of the set (YYYY-MM-DD).', S),
        'number': ('Collector number within the set (text: some are like "TG05" or "SV001").', S),
        'name': ('Card name (e.g. "Charizard ex", "Professor\'s Research").', S),
        'supertype': ('Pokémon, Trainer or Energy.', S),
        'subtypes': ('Subtypes such as Basic, Stage 1, Stage 2, ex, V, VMAX, Item, Supporter, Stadium.' + MULTI, S),
        'level': ('Pokémon level (Diamond & Pearl / Platinum era cards only).', S),
        'hp': ('Hit points (Pokémon cards only).', I),
        'types': ('Energy types of the Pokémon (Grass, Fire, Water, Lightning, Psychic, Fighting, Darkness, Metal, '
                  'Fairy, Dragon, Colorless).' + MULTI, S),
        'primary_type': ('First type of the Pokémon.', S),
        'evolves_from': ('Name of the card it evolves from.', S),
        'evolves_to': ('Names it can evolve into.' + MULTI, S),
        'rules': ('Rule boxes (e.g. the ex rule: "When your Pokémon ex is Knocked Out..."), joined with " | ".', S),
        'attack_count': ('Number of attacks (rows in card_attacks.csv).', I),
        'ability_count': ('Number of abilities (rows in card_abilities.csv).', I),
        'weakness_type': ('Weakness type.' + MULTI, S),
        'weakness_value': ('Weakness modifier (e.g. "×2", "+20").' + MULTI, S),
        'resistance_type': ('Resistance type.' + MULTI, S),
        'resistance_value': ('Resistance modifier (e.g. "-30").' + MULTI, S),
        'retreat_cost': ('Number of Energy needed to retreat.', I),
        'regulation_mark': ('Regulation mark (D, E, F, G, H, I, ...) used for Standard rotation.', S),
        'rarity': ('Rarity (e.g. Common, Rare Holo, Illustration Rare, Special Illustration Rare, Hyper Rare).', S),
        'artist': ('Illustrator.', S),
        'flavor_text': ('Pokédex-style flavor text printed on the card.', S),
        'national_numbers': ('National Pokédex numbers of the Pokémon on the card (several for TAG TEAM cards).' + MULTI, S),
        'ancient_trait': ('Ancient Trait name (XY Ancient Origins era).', S),
        'ancient_trait_text': ('Ancient Trait text.', S),
        'legal_standard': ('Standard format legality at the time of the snapshot (Legal, Not Legal, Banned or blank).', S),
        'legal_expanded': ('Expanded format legality.', S),
        'legal_unlimited': ('Unlimited format legality.', S),
        'image_small': ('URL of the small card image (hosted by the source; may stop working).', S),
        'image_large': ('URL of the high-resolution card image.', S),
    },
    'card_attacks.csv': {
        'attack_index': ('Position of the attack on the card (1 = first).', I),
        'name': ('Attack name.', S),
        'cost': ('Energy symbols in the attack cost.' + MULTI, S),
        'converted_energy_cost': ('Number of Energy symbols in the cost.', I),
        'damage': ('Damage as printed (e.g. "120", "30+", "10×"; blank for no damage).', S),
        'base_damage': ('Numeric part of the damage.', I),
        'damage_modifier': ('+ (can do more), × (multiplied) or - (can do less); blank for fixed damage.', S),
        'text': ('Attack effect text.', S),
    },
    'card_abilities.csv': {
        'ability_index': ('Position of the ability on the card.', I),
        'name': ('Ability name.', S),
        'type': ('Ability, Poké-Power, Poké-Body, Pokémon Power, Ancient Trait, ...', S),
        'text': ('Ability text.', S),
    },
    'card_pokemon.csv': {},
    'decks.csv': {
        'name': ('Theme deck name.', S),
        'types': ('Energy types of the deck.' + MULTI, S),
        'card_count': ('Cards in the deck (normally 60).', I),
    },
    'deck_cards.csv': {
        'card_name': ('Card name.', S),
        'rarity': ('Rarity of the printing in the deck.', S),
        'count': ('Copies in the deck.', I),
        'in_cards_table': ('1 if the card_id is in cards.csv (4 deck cards are not).', I),
    },
}
RESOURCES = {
    'sets.csv': 'One row per set (177), from Base Set (1999) to Delta Reign (November 2026).',
    'cards.csv': 'One row per English card (20,776): Pokémon, Trainer and Energy cards with HP, types, rarity, artist, legality and image links.',
    'card_attacks.csv': 'One row per attack: cost, damage (as printed and numeric) and effect text.',
    'card_abilities.csv': 'One row per Ability / Poké-Power / Poké-Body on a card.',
    'card_pokemon.csv': 'Bridge from cards to National Pokédex numbers; joins to The Complete Pokédex Dataset.',
    'decks.csv': 'One row per theme deck.',
    'deck_cards.csv': 'Card lists of the theme decks.',
}


def main():
    path = ROOT / 'dataset-metadata.json'
    resources = []
    for name, desc in RESOURCES.items():
        cols = list(pd.read_csv(DATA / name, nrows=0).columns)
        fields = []
        for c in cols:
            d = DOCS[name].get(c) or COMMON.get(c)
            if d is None:
                raise SystemExit(f'{name}: column {c} is not documented')
            fields.append({'name': c, 'description': d[0], 'type': d[1]})
        resources.append({'path': f'data/{name}', 'description': desc, 'schema': {'fields': fields}})
    resources.append({'path': 'data/tcg.sqlite', 'description': 'All tables in one SQLite database with keys.'})
    meta = {
        'title': 'The Complete Pokémon TCG Dataset',
        'subtitle': 'Every English Pokémon card 1999–2026: 20,776 cards, attacks & sets',
        'description': (ROOT / 'docs' / 'kaggle_description.md').read_text(),
        'id': 'cristobalmitchell/pokemon-tcg',
        'licenses': [{'name': 'other'}],
        'keywords': ['games', 'card games', 'pokemon', 'tabular', 'beginner', 'data visualization', 'nlp'],
        'expectedUpdateFrequency': 'never',
        'userSpecifiedSources': ('Compiled from the PokemonTCG/pokemon-tcg-data JSON files '
                                 '(https://github.com/PokemonTCG/pokemon-tcg-data), snapshot of November 2026. '
                                 'Card names, text and images are © The Pokémon Company, Nintendo, Creatures and GAME FREAK.'),
        'resources': resources,
    }
    path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + '\n')
    print(f'{len(resources)} resources, subtitle {len(meta["subtitle"])} chars')


if __name__ == '__main__':
    main()
