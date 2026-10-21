#!/usr/bin/env python3
"""Rewrites the tooltips of the talents, glyphs and set bonuses that mod-forever-periodic-crit turns
into "+10% crit chance on these ticks", in a client patch MPQ that carries Spell.dbc.

In stock their tooltips say the ticks "can now be critical strikes". With the module every tick can
crit, and these give ForeverPeriodicCrit.TalentBonus extra crit chance instead, so the text says so.
Only the English description of each row changes, in place: no row is added, moved or reordered,
and every other file in the patch is copied as it is. The glyph items' own spells share the glyph's
text, so they change too.

    python3 tools/build_patch.py --patch patch-with-spell-dbc.MPQ --out patch-new.MPQ [--bonus 10]

Without a patch to start from, --spell-dbc takes a stock DBFilesClient/Spell.dbc and --out gets a
new patch with only that file. Running it again on its own output changes nothing.

Needs Python 3 and StormLib (`STORMLIB`, default /usr/local/lib/libstorm.dylib).
"""

import argparse
import ctypes
import os
import struct
import sys
import tempfile

SPELL_DBC = "DBFilesClient\\Spell.dbc"
SPELL_FIELDS = 234
DESCRIPTION = 170          # enUS description

# Spell -> (stock tooltip, new tooltip). {bonus} is the crit chance the module adds.
TOOLTIPS = {
    63503: ("Grants the periodic damage from your Lacerate and Rip abilities the ability to critically hit.",
            "Increases the critical strike chance of the periodic damage from your Lacerate and Rip abilities by {bonus}."),
    58435: ("Grants the periodic damage from your Corruption and Unstable Affliction spells the ability to critically hit "
            "for $s1% increased damage, and increases the critical strike damage bonus of your Haunt spell by $s2%.",
            "Increases the critical strike chance of the periodic damage from your Corruption and Unstable Affliction "
            "spells by {bonus}, and increases the critical strike damage bonus of your Corruption, Unstable Affliction "
            "and Haunt spells by $s2%."),
    63091: ("The periodic damage from your Living Bomb can now be critical strikes.",
            "Increases the critical strike chance of the periodic damage from your Living Bomb by {bonus}."),
    63068: ("The periodic damage from your Explosive Trap can now be critical strikes.",
            "Increases the critical strike chance of the periodic damage from your Explosive Trap by {bonus}."),
    67118: ("Your Blood Plague ability now has a chance for its damage to be critical strikes.",
            "Increases the critical strike chance of your Blood Plague by {bonus}."),
    67125: ("Your Moonfire ability now has a chance for its periodic damage to be critical strikes.",
            "Increases the critical strike chance of the periodic damage from your Moonfire ability by {bonus}."),
    67128: ("Your Rejuvenation ability now has a chance for its healing to be critical strikes.",
            "Increases the critical effect chance of your Rejuvenation ability by {bonus}."),
    67150: ("The damage done by your Serpent Sting ability can now be critical strikes.",
            "Increases the critical strike chance of your Serpent Sting ability by {bonus}."),
    70726: ("Your Enrage ability no longer decreases your armor and instead decreases all damage taken by $70725s1%, "
            "and the periodic damage done by your Rake ability can now be a critical strike.",
            "Your Enrage ability no longer decreases your armor and instead decreases all damage taken by $70725s1%, "
            "and increases the critical strike chance of the periodic damage done by your Rake ability by {bonus}."),
}

# Glyphs: the glyph's aura and the spell its item casts both carry the text.
GLYPHS = (63091, 63068)


# --- Spell.dbc ------------------------------------------------------------------------------

def read_dbc(path):
    data = open(path, "rb").read()
    magic, count, fields, size, string_size = struct.unpack_from("<4s4I", data, 0)
    if magic != b"WDBC" or fields != SPELL_FIELDS or size != fields * 4:
        sys.exit("%s isn't a %d-field WDBC Spell.dbc" % (path, SPELL_FIELDS))
    rows = [list(struct.unpack_from("<%dI" % fields, data, 20 + i * size)) for i in range(count)]
    strings = bytearray(data[20 + count * size:20 + count * size + string_size])
    return rows, strings


def write_dbc(path, rows, strings):
    out = bytearray(struct.pack("<4s4I", b"WDBC", len(rows), SPELL_FIELDS, SPELL_FIELDS * 4, len(strings)))
    for row in rows:
        out += struct.pack("<%dI" % SPELL_FIELDS, *row)
    out += strings
    open(path, "wb").write(out)


def text_at(strings, offset):
    end = strings.index(b"\0", offset)
    return strings[offset:end].decode("utf-8")


def add_string(strings, text):
    offset = len(strings)
    strings += text.encode("utf-8") + b"\0"
    return offset


def patch_spell_dbc(path, bonus):
    rows, strings = read_dbc(path)
    by_id = {row[0]: row for row in rows}
    changed = []
    for spell_id, (stock, new) in TOOLTIPS.items():
        new = new.format(bonus="%g%%" % bonus)
        if spell_id not in by_id:
            sys.exit("Spell.dbc has no row %d" % spell_id)
        current = text_at(strings, by_id[spell_id][DESCRIPTION])
        if current == new:
            continue
        if current != stock:
            sys.exit("spell %d's tooltip isn't the stock one or this tool's:\n  %s" % (spell_id, current))

        targets = [row for row in rows if text_at(strings, row[DESCRIPTION]) == stock]
        if spell_id in GLYPHS and len(targets) < 2:
            sys.exit("glyph %d: found %d spells with its text, expected the glyph and its item spell" % (spell_id, len(targets)))
        offset = add_string(strings, new)
        for row in targets:
            row[DESCRIPTION] = offset
            changed.append(row[0])
    write_dbc(path, rows, strings)
    return changed


# --- MPQ ------------------------------------------------------------------------------------

def stormlib():
    lib = ctypes.CDLL(os.environ.get("STORMLIB", "/usr/local/lib/libstorm.dylib"))
    handle = ctypes.c_void_p
    lib.SFileOpenArchive.argtypes = [ctypes.c_char_p, ctypes.c_uint, ctypes.c_uint, ctypes.POINTER(handle)]
    lib.SFileCreateArchive.argtypes = [ctypes.c_char_p, ctypes.c_uint, ctypes.c_uint, ctypes.POINTER(handle)]
    lib.SFileExtractFile.argtypes = [handle, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
    lib.SFileAddFileEx.argtypes = [handle, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint]
    lib.SFileCloseArchive.argtypes = [handle]

    class FindData(ctypes.Structure):
        _fields_ = [("cFileName", ctypes.c_char * 1024), ("szPlainName", ctypes.c_char_p),
                    ("dwHashIndex", ctypes.c_uint), ("dwBlockIndex", ctypes.c_uint),
                    ("dwFileSize", ctypes.c_uint), ("dwFileFlags", ctypes.c_uint),
                    ("dwCompSize", ctypes.c_uint), ("dwFileTimeLo", ctypes.c_uint),
                    ("dwFileTimeHi", ctypes.c_uint), ("lcLocale", ctypes.c_uint)]

    lib.SFileFindFirstFile.argtypes = [handle, ctypes.c_char_p, ctypes.POINTER(FindData), ctypes.c_char_p]
    lib.SFileFindFirstFile.restype = handle
    lib.SFileFindNextFile.argtypes = [handle, ctypes.POINTER(FindData)]
    lib.SFileFindClose.argtypes = [handle]
    return lib, handle, FindData


def extract_all(mpq, folder):
    lib, handle, FindData = stormlib()
    h = handle()
    if not lib.SFileOpenArchive(mpq.encode(), 0, 0x100, ctypes.byref(h)):
        sys.exit("can't open %s" % mpq)

    names = []
    found = FindData()
    search = lib.SFileFindFirstFile(h, b"*", ctypes.byref(found), None)
    while search:
        names.append(found.cFileName.decode())
        if not lib.SFileFindNextFile(search, ctypes.byref(found)):
            break
    if search:
        lib.SFileFindClose(search)

    files = []
    for name in names:
        if name in ("(listfile)", "(attributes)", "(signature)"):
            continue
        dst = os.path.join(folder, *name.split("\\"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if not lib.SFileExtractFile(h, name.encode(), dst.encode(), 0):
            sys.exit("can't extract %s" % name)
        files.append((dst, name))
    lib.SFileCloseArchive(h)
    return files


def pack(out, files):
    lib, handle, _ = stormlib()
    if os.path.exists(out):
        os.remove(out)
    h = handle()
    # MPQ v1 with a listfile and attributes; each file zlib-compressed, like other client patches.
    if not lib.SFileCreateArchive(out.encode(), 0x00300000, max(16, len(files) * 2), ctypes.byref(h)):
        sys.exit("can't create %s" % out)
    for src, name in files:
        if not lib.SFileAddFileEx(h, src.encode(), name.encode(), 0x80000200, 0x02, 0x02):
            sys.exit("can't add %s" % name)
    lib.SFileCloseArchive(h)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = ap.add_mutually_exclusive_group(required=True)
    source.add_argument("--patch", help="a client patch MPQ that carries DBFilesClient\\Spell.dbc")
    source.add_argument("--spell-dbc", help="a stock Spell.dbc, for a new patch with only that file")
    ap.add_argument("--out", required=True)
    ap.add_argument("--bonus", type=float, default=10.0, help="ForeverPeriodicCrit.TalentBonus (default 10)")
    args = ap.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        if args.patch:
            files = extract_all(args.patch, tmp)
        else:
            dst = os.path.join(tmp, "DBFilesClient", "Spell.dbc")
            os.makedirs(os.path.dirname(dst))
            open(dst, "wb").write(open(args.spell_dbc, "rb").read())
            files = [(dst, SPELL_DBC)]

        spell = next((local for local, name in files if name.lower() == SPELL_DBC.lower()), None)
        if not spell:
            sys.exit("%s has no %s" % (args.patch, SPELL_DBC))
        changed = patch_spell_dbc(spell, args.bonus)
        pack(args.out, files)

    print("%s: %d tooltips changed%s" % (args.out, len(changed), (": " + ", ".join(map(str, changed))) if changed else ""))


if __name__ == "__main__":
    main()
