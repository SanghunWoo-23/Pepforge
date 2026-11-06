"""PyMOL native sequence-row aliases with lossless full chemical token mapping.

PyMOL's builtin sequence display cannot show arbitrary-length token strings;
this exporter explicitly uses unique <=3-character labels and TSV lookup.
"""
import csv
from pathlib import Path

_ALPHABET='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
def _alias(index):
    if not 0<=index<36**3: raise ValueError('Too many chemical tokens')
    return _ALPHABET[index//1296]+_ALPHABET[(index//36)%36]+_ALPHABET[index%36]

def export_pymol_token_view(pdb_file, token_csv, output_prefix):
    source=Path(pdb_file); token_file=Path(token_csv); prefix=Path(output_prefix)
    if not source.is_file() or not token_file.is_file(): raise FileNotFoundError('PDB and token CSV are required')
    with token_file.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f); rows=list(reader)
    if not rows or not {'resi','token'}.issubset(reader.fieldnames or []):
        raise ValueError('Token CSV must contain resi,token columns')
    # Each residue must already exist in the PDB; don't fabricate chemistry.
    original=source.read_text(errors='replace').splitlines(keepends=True)
    residues={line[22:27].strip() for line in original if line.startswith(('ATOM  ','HETATM'))}
    mapping={}
    for row in rows:
        key=str(row['resi']).strip(); token=str(row['token']).strip()
        if not key or not token or key in mapping or key not in residues:
            raise ValueError(f'Invalid, duplicate or absent residue: {key}')
        mapping[key]=(token,_alias(len(mapping)))
    altered=[]
    for line in original:
        if line.startswith(('ATOM  ','HETATM')) and line[22:27].strip() in mapping:
            line=line[:17]+mapping[line[22:27].strip()][1]+line[20:]
        altered.append(line)
    prefix.parent.mkdir(parents=True,exist_ok=True)
    pdb=prefix.with_suffix('.pdb');pml=prefix.with_suffix('.pml');tsv=prefix.with_suffix('.tsv')
    pdb.write_text(''.join(altered))
    with tsv.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.writer(f,delimiter='\t');w.writerow(['resi','display_alias','full_chemical_token'])
        for k,(token,alias) in mapping.items():w.writerow([k,alias,token])
    # PyMOL will display each three-character alias in its native top sequence row.
    # Full tokens remain in the mapping file rather than being silently truncated.
    pml.write_text('load "'+pdb.resolve().as_posix()+'", Pepforge_Modified\nset seq_view, 1\nset seq_view_format, 1\nset seq_view_label_mode, 1\nsort Pepforge_Modified\n',encoding='utf-8')
    from .v6_pymol_full_token_panel import export_full_token_panel
    plugin=prefix.parent/(prefix.name+'_full_tokens.py')
    panel=export_full_token_panel(tsv,plugin)
    with pml.open('a',encoding='utf-8') as script:
        script.write('run "'+plugin.resolve().as_posix()+'"\npepforge_tokens\n')
    return {'pdb':str(pdb),'pml':str(pml),'mapping_tsv':str(tsv),'full_token_panel':panel['plugin_python'],'exact_full_length_native_sequence_labels':False}
