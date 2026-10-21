# Forever Periodic Crit

An [AzerothCore](https://www.azerothcore.org/) (WotLK 3.3.5a) module that lets damage-over-time
and heal-over-time ticks crit, as in WoW Forever. No SQL; the client patch is optional and only
updates tooltips.

## What changes

In stock 3.3.5 a tick only crits when a talent, glyph or set bonus says so: Shadowform, Pandemic,
Primal Gore (Rip and Lacerate), Glyph of Living Bomb, Glyph of Explosive Trap, Flame Shock,
Rupture, and a few tier sets. Every other DoT and HoT never crits. With this module, each tick of
a player's periodic spell rolls for a crit:

- **DoTs**: Corruption, Immolate, Moonfire, Insect Swarm, Living Bomb, Holy Fire,
  Pyroblast's and Fireball's burn, Mind Flay, Drain Life, Devouring Plague, Consecration, Blood
  Plague and Frost Fever, and the rest.
- **Bleeds and poisons**: Rend, Rip, Rake, Lacerate, Garrote, Deadly Poison, Serpent Sting,
  pet bleeds.
- **HoTs**: Renew, Rejuvenation, Regrowth, Lifebloom, Wild Growth, Riptide, Earthliving,
  Lightwell Renew, Mend Pet.

Each tick uses the crit chance a direct hit of that spell would have: spell crit for its school
(spells, poisons, Immolation Trap), melee crit for melee bleeds, ranged crit for Serpent Sting,
Black Arrow and Explosive Trap. Talents and glyphs that raise a
spell's crit chance count, and so do the target's resilience and crit-taken debuffs. The talents,
glyphs and set bonuses that let ticks crit in stock add +10% on top (see below).

A crit tick does what a direct crit of the same kind does: spells +50%, melee and ranged
abilities +100%, plus talents that raise crit damage (Shadow Power, Mortal Shots and so on). The
combat log and scrolling combat text show tick crits like any other crit.

Players, their pets and totems get this. NPC DoTs and HoTs don't crit, as in stock.

### Never crit

- Ticks that are already made from a crit or from a heal that could crit, so a second crit would
  count it twice: Ignite, Deep Wounds, Righteous Vengeance, Sheath of Light, Languish, Piercing
  Shots, Blessed Recovery, Holy Mending, and the Glyph of Flash of Light and Glyph of Prayer of
  Healing HoTs. They're the default `ExcludeSpells`.
- Spells the core already marks as unable to crit, like Unholy Blight.
- Where stock lets one of these crit anyway (Righteous Vengeance with the Retribution T9 2-piece),
  that still works: the list only stops this module from adding a crit.
- Passive auras, and by default anything that isn't a class spell: bandages, food, potions,
  item and enchant effects (see `ClassSpellsOnly`).

Channeled and ground spells that hit through a triggered spell, like Arcane Missiles, Blizzard,
Hurricane, Rain of Fire, Volley, Tranquility and Healing Stream Totem, could already crit and
aren't changed.

### Talents, glyphs and set bonuses that let ticks crit

In stock these were the only way for those ticks to crit. With every tick able to crit they would
do nothing, so each one gives **+10% crit chance** on the ticks it names instead
(`ForeverPeriodicCrit.TalentBonus`):

| Source | Class | Ticks |
|---|---|---|
| Primal Gore (talent) | Druid | Rip, Lacerate |
| Pandemic (talent) | Warlock | Corruption, Unstable Affliction (its +100% crit damage on them and Haunt stays) |
| Glyph of Living Bomb | Mage | Living Bomb |
| Glyph of Explosive Trap | Hunter | Explosive Trap |
| T9 melee 4-piece | Death Knight | Blood Plague |
| T9 Balance 2-piece | Druid | Moonfire |
| T9 Restoration 4-piece | Druid | Rejuvenation |
| T9 2-piece | Hunter | Serpent Sting |
| T10 Feral 4-piece | Druid | Rake (the Enrage part is unchanged) |

Shadowform, Flame Shock (every shaman has its "can crit" passive) and Rupture come with the
class, so they give no bonus (`TalentBonusExclude`). The Retribution T9 2-piece still lets
Righteous Vengeance crit, which this module never does on its own.

Talents that already raised a DoT's crit chance, like Malediction and Mind Melt, keep doing that.

## Client patch (optional)

The client shows its own tooltips, which still say these ticks "can now be critical strikes".
`tools/build_patch.py` rewrites them to say +10%. It changes only the English description of
those spells (and of the two glyph items' spells) in Spell.dbc, in place:

```bash
# On a patch that already carries Spell.dbc (keeps every other file):
python3 tools/build_patch.py --patch patch-with-spell-dbc.MPQ --out patch-new.MPQ
# Or on a stock Spell.dbc, for a patch with only that file:
python3 tools/build_patch.py --spell-dbc DBFilesClient/Spell.dbc --out patch-T.MPQ
```

`--bonus` sets the number the tooltips show, if `TalentBonus` isn't 10. Without the patch
everything works the same; only the tooltips are out of date. Needs Python 3 and StormLib
(`STORMLIB`, default `/usr/local/lib/libstorm.dylib`).

## Requirements

- [AzerothCore](https://github.com/azerothcore/azerothcore-wotlk) `master` (WotLK 3.3.5a)
- A WoW 3.3.5a (12340) client
- No SQL. The client patch only updates tooltips.

## Install

Clone it into your AzerothCore `modules` folder **as `mod-forever-periodic-crit`**, without the
repo's `wow-` prefix. AzerothCore finds the module's entry point from the folder name.

```bash
cd <azerothcore>/modules
git clone https://github.com/buildthehomelab/wow-mod-forever-periodic-crit.git mod-forever-periodic-crit
```

Rebuild the worldserver, then copy `conf/mod_forever_periodic_crit.conf.dist` to your config
folder as `mod_forever_periodic_crit.conf`.

## Settings

| Setting | Default | What it does |
|---------|---------|--------------|
| `ForeverPeriodicCrit.Enable` | `1` | Master switch. With `0`, ticks crit only where stock 3.3.5 lets them. |
| `ForeverPeriodicCrit.Damage` | `1` | Damage ticks (DoTs, bleeds, poisons, drains) can crit. |
| `ForeverPeriodicCrit.Healing` | `1` | HoT ticks can crit. |
| `ForeverPeriodicCrit.ClassSpellsOnly` | `1` | Only class spells and pet abilities crit. `0` lets item, enchant, bandage and other non-class DoTs/HoTs crit too. |
| `ForeverPeriodicCrit.UseSpellCrit` | `7001,55095` | Spells with no damage class that should crit with the caster's spell crit. The core never lets a spell with no damage class crit, so they need listing. Defaults: Lightwell Renew, Frost Fever. |
| `ForeverPeriodicCrit.ExcludeSpells` | see above | Spells that never crit. |
| `ForeverPeriodicCrit.TalentBonus` | `10` | Extra crit chance on the ticks a talent, glyph or set bonus above covers. `0` turns it off. |
| `ForeverPeriodicCrit.TalentBonusExclude` | `49868,75461,17834,75445` | "Can crit" auras that give no bonus: Shadowform, Flame Shock Passive, Improved Immolate rank 3's hidden Conflagrate entry, Demonic Immolate (NPC). |

All of them can be changed with `.reload config`. DoTs and HoTs already running keep the chance
they had until they're refreshed or cast again.

## How it works

The core gives every periodic aura a crit chance when it's created, refreshed or stacked, and
rolls it on each tick. That chance is 0 unless an "ability periodic crit" aura, which only the
talents, glyphs and set bonuses above carry, covers the spell. Right after the core sets it, AzerothCore calls the
`OnAuraApply` unit hook; the module works out the chance a direct hit of the spell would have,
using the same core functions as a direct hit, adds `TalentBonus` when one of the caster's
"ability periodic crit" auras covers the spell, and sets it on the aura's damage and heal effects.
Like the core, it takes the chance once when the aura goes on, so a DoT keeps the crit chance
you had when you cast it.

## Things to know

- **Crit procs.** A tick crit counts as a crit for procs that react to periodic damage or
  healing. In stock that already happens with the DoTs listed at the top; now it happens with
  every DoT and HoT. The procs in the server's `spell_proc` table that react to periodic crits are
  Ignite and Burnout (fire DoT crits from Living Bomb, Pyroblast, Fireball, Flamestrike), Honor
  Among Thieves (party members' tick crits give combo points, still with its own cooldown),
  Surge of Light (HoT crits), Savage Defense (Lacerate and Rake crits), Hunting Party, Expose
  Weakness and Go for the Throat (Serpent Sting and trap crits), and Soul of the Dead. WoW
  Forever has some of its own rules here (a bleed crit doesn't trigger Bloodthirst, Inspiration
  only comes from direct heals); this module doesn't copy those.
- **Damage class.** Blood Plague is a melee-class spell in the 3.3.5 data, so it crits with
  melee crit for +100%. Frost Fever has no damage class, so through `UseSpellCrit` it crits with
  frost spell crit for +50%.
- WoW Forever also halved crit damage in PvP for a while, but Blizzard called that a bug. This
  module doesn't do it.
- Playerbots get it too, since they're players.

## Troubleshooting

- **A DoT or HoT doesn't crit.** One that is already running keeps the crit chance it had when it
  was cast, until it is refreshed or cast again.
- **An item, enchant or bandage DoT or HoT doesn't crit.** Only class spells and pet abilities do
  by default; set `ForeverPeriodicCrit.ClassSpellsOnly = 0` to include the rest.
- **A spell with no damage class never crits.** The core doesn't allow it. List it in
  `ForeverPeriodicCrit.UseSpellCrit` to crit with the caster's spell crit (Lightwell Renew and
  Frost Fever are listed by default).

## Credits

Author: [buildthehomelab](https://github.com/buildthehomelab)

The design follows the WoW Forever private server ruleset. The code is original.

## License

MIT. See [LICENSE](LICENSE).
