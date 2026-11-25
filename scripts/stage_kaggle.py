"""Stage a Kaggle upload of The Complete Pokémon TCG Dataset for the web uploader.

Creates kaggle_upload/ (ignored by git):

    kaggle_upload/dataset/        everything to upload: the CSV files and tcg.sqlite, laid out as on Kaggle
    kaggle_upload/UPLOAD.md       step-by-step guide for the web uploader
    kaggle_upload/COLUMNS.md      every column description, per file, ready to paste into the Data Card
    kaggle_upload/description.md  the dataset description (paste into "About Dataset")
    kaggle_upload/cover.png       the cover image
    kaggle_upload/notebook.ipynb  the starter notebook, to publish as a Kaggle notebook on the dataset
    kaggle_upload/metadata/dataset-metadata.json   for the optional Kaggle CLI shortcut

Usage:
    python scripts/stage_kaggle.py
"""

import json
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
OUT = ROOT / 'kaggle_upload'


def place(src, dst):
    """Hard-link when possible (no extra disk), copy otherwise."""
    dst.unlink(missing_ok=True)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def columns_markdown(meta):
    lines = ['# Column descriptions', '',
             "Paste these into each file's column descriptions on the Kaggle Data Card "
             '(Data Explorer → file → Columns → edit).', '']
    for r in meta['resources']:
        lines += [f'## {r["path"]}', '', r['description'], '']
        for f in r.get('schema', {}).get('fields', []):
            lines.append(f'- **{f["name"]}** ({f["type"]}): {f["description"]}')
        lines.append('')
    return '\n'.join(lines)


def upload_guide(meta, files):
    return f"""# Uploading {meta['title']} with the Kaggle web uploader

## 1. Create the dataset
1. On Kaggle choose **Create → New Dataset** (for later updates: open the dataset → **New Version**).
2. Drag in **everything in `kaggle_upload/dataset/`** ({len(files)} files).
3. Title: **{meta['title']}**. Set the URL slug to `{meta['id'].split('/')[1]}` so it matches
   `{meta['id']}` (the Pokédex dataset and the notebook link to that address).
4. Create it. It can start private; make it public when you are ready.

## 2. Settings and Data Card
| Field | Value |
|---|---|
| Subtitle | {meta['subtitle']} |
| About Dataset (description) | paste `description.md` |
| License | Other (specified in description). The terms are in the description's "License" section |
| Tags | {', '.join(meta['keywords'])} |
| Cover image | `cover.png` (1280 × 640) |
| Expected update frequency | {meta['expectedUpdateFrequency']} (a snapshot of a source that is no longer updated) |
| Provenance / sources | {meta['userSpecifiedSources']} |

## 3. Column descriptions
Kaggle's usability score counts file and column descriptions. Paste them from `COLUMNS.md`
(Data Explorer → choose a file → Columns → edit each description).

**Optional shortcut:** with the Kaggle CLI installed and an API token configured:

    kaggle datasets metadata --update -p kaggle_upload/metadata {meta['id']}

(check `kaggle datasets metadata --help` for your CLI version).

## 4. Starter notebook
On the dataset page choose **New Notebook → File → Import Notebook**, pick `notebook.ipynb`, add
**The Complete Pokédex Dataset** as a second input (section 6 joins it), run all, and publish it.
"""


def main():
    meta = json.loads((ROOT / 'dataset-metadata.json').read_text())
    if OUT.exists():
        shutil.rmtree(OUT)
    ds = OUT / 'dataset'
    ds.mkdir(parents=True)
    files = []
    for p in sorted(DATA.glob('*.csv')) + [DATA / 'tcg.sqlite']:
        place(p, ds / p.name)
        files.append(p.name)
    documented = {r['path'] for r in meta['resources']}
    if set(files) - documented:
        raise SystemExit(f'files without a dataset-metadata.json resource: {sorted(set(files) - documented)}')
    (OUT / 'metadata').mkdir()
    shutil.copy2(ROOT / 'dataset-metadata.json', OUT / 'metadata' / 'dataset-metadata.json')
    shutil.copy2(ROOT / 'docs' / 'kaggle_description.md', OUT / 'description.md')
    shutil.copy2(ROOT / 'dataset-cover-image.png', OUT / 'cover.png')
    shutil.copy2(ROOT / 'notebooks' / 'pokemon_tcg_eda.ipynb', OUT / 'notebook.ipynb')
    (OUT / 'COLUMNS.md').write_text(columns_markdown(meta))
    (OUT / 'UPLOAD.md').write_text(upload_guide(meta, files))
    size = sum(p.stat().st_size for p in ds.iterdir()) / 1e6
    print(f'kaggle_upload/dataset: {len(files)} files, {size:,.0f} MB; guide in kaggle_upload/UPLOAD.md')


if __name__ == '__main__':
    main()
