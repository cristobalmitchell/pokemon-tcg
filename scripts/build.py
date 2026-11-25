"""Build The Complete Pokémon TCG Dataset from the pokemon-tcg-data JSON files.

    data/sets.csv            one row per set (expansion)
    data/cards.csv           one row per card
    data/card_attacks.csv    one row per attack on a card
    data/card_abilities.csv  one row per ability (Ability, Poké-Power, Poké-Body, ...) on a card
    data/card_pokemon.csv    card -> National Pokédex number (joins to The Complete Pokédex Dataset)
    data/decks.csv           one row per theme deck
    data/deck_cards.csv      one row per card line in a theme deck
    data/tcg.sqlite          all of the above in one SQLite database

Source: https://github.com/PokemonTCG/pokemon-tcg-data (English, v2 JSON). That project is frozen
for historical use; this build is a snapshot of it.

Usage:
    git clone --depth 1 https://github.com/PokemonTCG/pokemon-tcg-data.git
    python scripts/build.py pokemon-tcg-data
"""

import json
import re
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
SEP = '|'  # separator for multi-valued cells (types, subtypes, energy costs, ...)


def joined(values):
    return SEP.join(values) if values else None


def legal(card, fmt):
    return (card.get('legalities') or {}).get(fmt)


def iso_date(s):
    return s.replace('/', '-') if isinstance(s, str) else s


def load(src):
    sets = json.loads((src / 'sets' / 'en.json').read_text())
    cards = []
    for path in sorted((src / 'cards' / 'en').glob('*.json')):
        cards += json.loads(path.read_text())
    decks = []
    for path in sorted((src / 'decks' / 'en').glob('*.json')):
        decks += json.loads(path.read_text())
    return sets, cards, decks


def build_sets(sets, cards):
    per_set = pd.Series([c['id'].rsplit('-', 1)[0] for c in cards]).value_counts()
    rows = [{
        'set_id': s['id'],
        'name': s['name'],
        'series': s['series'],
        'printed_total': s.get('printedTotal'),
        'total': s.get('total'),
        'card_count': int(per_set.get(s['id'], 0)),
        'ptcgo_code': s.get('ptcgoCode'),
        'release_date': iso_date(s.get('releaseDate')),
        'updated_at': iso_date(s.get('updatedAt')),
        'legal_standard': (s.get('legalities') or {}).get('standard'),
        'legal_expanded': (s.get('legalities') or {}).get('expanded'),
        'legal_unlimited': (s.get('legalities') or {}).get('unlimited'),
        'symbol_url': (s.get('images') or {}).get('symbol'),
        'logo_url': (s.get('images') or {}).get('logo'),
    } for s in sets]
    return pd.DataFrame(rows).sort_values(['release_date', 'set_id']).reset_index(drop=True)


def damage_parts(text):
    """'120+' -> (120, '+'); '30×' -> (30, '×'); '' -> (None, None)."""
    m = re.match(r'^(\d+)\s*([+×x\-]?)$', (text or '').strip())
    if not m:
        return None, None
    return int(m.group(1)), (m.group(2).replace('x', '×') or None)


def build_cards(cards, sets):
    set_info = sets.set_index('set_id')
    rows, attacks, abilities, pokemon = [], [], [], []
    for c in cards:
        set_id = c['id'].rsplit('-', 1)[0]
        weak, res = c.get('weaknesses') or [], c.get('resistances') or []
        trait = c.get('ancientTrait') or {}
        rows.append({
            'card_id': c['id'],
            'set_id': set_id,
            'set_name': set_info.loc[set_id, 'name'],
            'series': set_info.loc[set_id, 'series'],
            'release_date': set_info.loc[set_id, 'release_date'],
            'number': c['number'],
            'name': c['name'],
            'supertype': c['supertype'],
            'subtypes': joined(c.get('subtypes')),
            'level': c.get('level'),
            'hp': int(c['hp']) if str(c.get('hp', '')).isdigit() else None,
            'types': joined(c.get('types')),
            'primary_type': (c.get('types') or [None])[0],
            'evolves_from': c.get('evolvesFrom'),
            'evolves_to': joined(c.get('evolvesTo')),
            'rules': ' | '.join(c['rules']) if c.get('rules') else None,
            'attack_count': len(c.get('attacks') or []),
            'ability_count': len(c.get('abilities') or []),
            'weakness_type': joined([w['type'] for w in weak]),
            'weakness_value': joined([w['value'] for w in weak]),
            'resistance_type': joined([r['type'] for r in res]),
            'resistance_value': joined([r['value'] for r in res]),
            'retreat_cost': c.get('convertedRetreatCost'),
            'regulation_mark': c.get('regulationMark'),
            'rarity': c.get('rarity'),
            'artist': c.get('artist'),
            'flavor_text': c.get('flavorText'),
            'national_numbers': joined([str(n) for n in c.get('nationalPokedexNumbers') or []]),
            'ancient_trait': trait.get('name'),
            'ancient_trait_text': trait.get('text'),
            'legal_standard': legal(c, 'standard'),
            'legal_expanded': legal(c, 'expanded'),
            'legal_unlimited': legal(c, 'unlimited'),
            'image_small': (c.get('images') or {}).get('small'),
            'image_large': (c.get('images') or {}).get('large'),
        })
        for i, a in enumerate(c.get('attacks') or [], 1):
            dmg, mod = damage_parts(a.get('damage'))
            cost = a.get('cost') or []
            # A 'Free' cost is zero Energy; the source counts it as 1 on two cards.
            converted = 0 if cost == ['Free'] else a.get('convertedEnergyCost')
            attacks.append({
                'card_id': c['id'], 'attack_index': i, 'name': a['name'], 'cost': joined(cost),
                'converted_energy_cost': converted, 'damage': a.get('damage') or None,
                'base_damage': dmg, 'damage_modifier': mod, 'text': a.get('text') or None,
            })
        for i, a in enumerate(c.get('abilities') or [], 1):
            kind = {'Poké-POWER': 'Poké-Power', 'Poké-BODY': 'Poké-Body'}.get(a.get('type'), a.get('type'))
            abilities.append({'card_id': c['id'], 'ability_index': i, 'name': a['name'], 'type': kind,
                              'text': a.get('text')})
        for n in c.get('nationalPokedexNumbers') or []:
            pokemon.append({'card_id': c['id'], 'national_number': n})
    cards_df = pd.DataFrame(rows)
    cards_df['_n'] = cards_df.number.str.extract(r'(\d+)', expand=False).astype(float)
    cards_df = (cards_df.merge(sets[['set_id']].reset_index().rename(columns={'index': '_s'}), on='set_id')
                .sort_values(['_s', '_n', 'number']).drop(columns=['_s', '_n']).reset_index(drop=True))
    for col in ('hp', 'retreat_cost'):
        cards_df[col] = cards_df[col].astype('Int64')
    attacks = pd.DataFrame(attacks)
    for col in ('base_damage', 'converted_energy_cost'):
        attacks[col] = attacks[col].astype('Int64')
    return cards_df, attacks, pd.DataFrame(abilities), pd.DataFrame(pokemon).drop_duplicates()


def build_decks(decks, cards):
    known = set(cards.card_id)
    deck_rows, lines = [], []
    for d in decks:
        deck_rows.append({
            'deck_id': d['id'],
            'name': d['name'],
            'types': joined(d.get('types')),
            'set_id': d['id'][2:].rsplit('-', 1)[0],
            'card_count': sum(c['count'] for c in d['cards']),
        })
        for c in d['cards']:
            lines.append({'deck_id': d['id'], 'card_id': c['id'], 'card_name': c['name'],
                          'rarity': c.get('rarity'), 'count': c['count'], 'in_cards_table': int(c['id'] in known)})
    return pd.DataFrame(deck_rows), pd.DataFrame(lines)


def write_sqlite(tables):
    path = DATA / 'tcg.sqlite'
    path.unlink(missing_ok=True)
    con = sqlite3.connect(path)
    pk = {'sets': 'set_id', 'cards': 'card_id', 'decks': 'deck_id'}
    fk = {'cards': [('set_id', 'sets')], 'card_attacks': [('card_id', 'cards')], 'card_abilities': [('card_id', 'cards')],
          'card_pokemon': [('card_id', 'cards')], 'decks': [('set_id', 'sets')], 'deck_cards': [('deck_id', 'decks')]}
    for name, df in tables.items():
        cols = []
        for c in df.columns:
            t = 'INTEGER' if pd.api.types.is_integer_dtype(df[c]) else 'REAL' if pd.api.types.is_float_dtype(df[c]) else 'TEXT'
            cols.append(f'"{c}" {t}' + (' PRIMARY KEY' if pk.get(name) == c else ''))
        for col, ref in fk.get(name, []):
            cols.append(f'FOREIGN KEY ("{col}") REFERENCES {ref}("{col}")')
        con.execute(f'CREATE TABLE {name} ({", ".join(cols)})')
        con.executemany(f'INSERT INTO {name} VALUES ({", ".join("?" * len(df.columns))})',
                        df.astype(object).where(df.notna(), None).itertuples(index=False, name=None))
    for sql in ['CREATE INDEX ix_cards_set ON cards(set_id)', 'CREATE INDEX ix_attacks_card ON card_attacks(card_id)',
                'CREATE INDEX ix_pokemon_card ON card_pokemon(card_id)',
                'CREATE INDEX ix_pokemon_number ON card_pokemon(national_number)']:
        con.execute(sql)
    con.commit()
    con.execute('VACUUM')
    con.close()


def main(src):
    src = Path(src)
    raw_sets, raw_cards, raw_decks = load(src)
    sets = build_sets(raw_sets, raw_cards)
    cards, attacks, abilities, pokemon = build_cards(raw_cards, sets)
    decks, deck_cards = build_decks(raw_decks, cards)
    tables = {'sets': sets, 'cards': cards, 'card_attacks': attacks, 'card_abilities': abilities,
              'card_pokemon': pokemon, 'decks': decks, 'deck_cards': deck_cards}
    DATA.mkdir(exist_ok=True)
    for name, df in tables.items():
        df.to_csv(DATA / f'{name}.csv', index=False)
    write_sqlite(tables)
    print(', '.join(f'{k} {v.shape}' for k, v in tables.items()))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'pokemon-tcg-data')
