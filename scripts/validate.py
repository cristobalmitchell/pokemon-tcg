"""Integrity checks for The Complete Pokémon TCG Dataset. Run before every Kaggle upload:

    python scripts/validate.py
"""

import json
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
ENERGY = {'Colorless', 'Darkness', 'Dragon', 'Fairy', 'Fighting', 'Fire', 'Grass', 'Lightning', 'Metal',
          'Psychic', 'Water', 'Free'}
failures = []


def check(ok, message):
    if not ok:
        failures.append(message)


def read(name):
    return pd.read_csv(DATA / f'{name}.csv', low_memory=False)


def main():
    sets, cards, attacks, abilities = read('sets'), read('cards'), read('card_attacks'), read('card_abilities')
    pokemon, decks, deck_cards = read('card_pokemon'), read('decks'), read('deck_cards')

    check(sets.set_id.is_unique and sets.name.notna().all(), 'sets: set_id not unique or name missing')
    check(pd.to_datetime(sets.release_date, errors='coerce').notna().all(), 'sets: bad release_date')
    check((sets.card_count == cards.groupby('set_id').size().reindex(sets.set_id).fillna(0).values).all(),
          'sets: card_count disagrees with cards')

    check(cards.card_id.is_unique, 'cards: card_id not unique')
    check(cards.set_id.isin(sets.set_id).all(), 'cards: unknown set_id')
    check(cards.supertype.isin(['Pokémon', 'Trainer', 'Energy']).all(), 'cards: unknown supertype')
    poke = cards[cards.supertype == 'Pokémon']
    check(poke.hp.notna().all() and poke.hp.between(10, 400).all(), 'cards: Pokémon card with missing or odd HP')
    # Trainer cards can have HP (Fossils and Clefairy Doll are played as Pokémon); Energy cards cannot.
    check(cards[cards.supertype == 'Energy'].hp.isna().all(), 'cards: HP on an Energy card')
    types = set(cards.types.dropna().str.split('|').explode())
    check(types <= ENERGY, f'cards: unknown type {types - ENERGY}')
    for col in ('legal_standard', 'legal_expanded', 'legal_unlimited'):
        check(cards[col].dropna().isin(['Legal', 'Banned', 'Not Legal']).all(), f'cards: bad {col}')
    check((cards.attack_count == attacks.groupby('card_id').size().reindex(cards.card_id).fillna(0).values).all(),
          'cards: attack_count disagrees with card_attacks')

    check(attacks.card_id.isin(cards.card_id).all(), 'card_attacks: unknown card_id')
    check(not attacks.duplicated(['card_id', 'attack_index']).any(), 'card_attacks: duplicate attack_index')
    costs = set(attacks.cost.dropna().str.split('|').explode())
    check(costs <= ENERGY, f'card_attacks: unknown energy {costs - ENERGY}')
    priced = attacks[attacks.cost.notna()]  # two attacks have no cost listed in the source
    check((priced.cost.str.split('|').map(lambda c: len([x for x in c if x != 'Free']))
           == priced.converted_energy_cost).all(), 'card_attacks: converted_energy_cost != number of energy symbols')
    check(attacks.base_damage.dropna().between(0, 2000).all(), 'card_attacks: base_damage out of range')
    check(abilities.card_id.isin(cards.card_id).all(), 'card_abilities: unknown card_id')

    check(pokemon.card_id.isin(cards.card_id).all(), 'card_pokemon: unknown card_id')
    check(pokemon.national_number.between(1, 1025).all(), 'card_pokemon: national_number outside 1..1025')
    check(not pokemon.duplicated().any(), 'card_pokemon: duplicate rows')

    check(decks.deck_id.is_unique and decks.set_id.isin(sets.set_id).all(), 'decks: duplicate id or unknown set')
    check(deck_cards.deck_id.isin(decks.deck_id).all(), 'deck_cards: unknown deck_id')
    check((deck_cards.in_cards_table == deck_cards.card_id.isin(cards.card_id).astype(int)).all(),
          'deck_cards: in_cards_table flag wrong')
    check((decks.card_count == deck_cards.groupby('deck_id')['count'].sum().reindex(decks.deck_id).values).all(),
          'decks: card_count disagrees with deck_cards')

    con = sqlite3.connect(DATA / 'tcg.sqlite')
    for name, df in [('sets', sets), ('cards', cards), ('card_attacks', attacks), ('card_abilities', abilities),
                     ('card_pokemon', pokemon), ('decks', decks), ('deck_cards', deck_cards)]:
        n = con.execute(f'SELECT COUNT(*) FROM {name}').fetchone()[0]
        check(n == len(df), f'tcg.sqlite: {name} has {n} rows, CSV has {len(df)}')
    fk = con.execute('PRAGMA foreign_key_check').fetchall()
    check(not fk, f'tcg.sqlite: {len(fk)} foreign key violations')
    con.close()

    meta = json.loads((ROOT / 'dataset-metadata.json').read_text())
    check(6 <= len(meta['title']) <= 50 and 20 <= len(meta['subtitle']) <= 80, 'metadata: title/subtitle length')
    documented = {r['path']: [f['name'] for f in r.get('schema', {}).get('fields', [])] for r in meta['resources']}
    for p in sorted(DATA.glob('*.csv')):
        cols = list(pd.read_csv(p, nrows=0).columns)
        check(documented.get(f'data/{p.name}') == cols, f'metadata: data/{p.name} columns not documented in order')

    if failures:
        print(f'FAILED {len(failures)} check(s):')
        for f in failures:
            print('  -', f)
        sys.exit(1)
    print(f'OK: {len(sets)} sets, {len(cards):,} cards, {len(attacks):,} attacks, {len(abilities):,} abilities, '
          f'{len(pokemon):,} card-to-Pokédex links, {len(decks)} decks')


if __name__ == '__main__':
    main()
