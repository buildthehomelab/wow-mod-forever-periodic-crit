/*
 * mod-forever-periodic-crit
 *
 * Damage-over-time and heal-over-time ticks can crit, as in WoW Forever. In stock 3.3.5 a tick
 * only crits when a talent, glyph or set bonus says so (Shadowform, Pandemic, Primal Gore, Flame
 * Shock, Rupture and a few others); every other DoT and HoT never does. With this module, every
 * tick of a player's DoT, bleed, drain or HoT rolls for a crit with the caster's crit chance for
 * that spell.
 *
 * No client patch: the server decides crits on its own and the 3.3.5 combat log already shows
 * periodic crits.
 *
 * Released under the MIT License.
 */

#include "Config.h"
#include "Player.h"
#include "ScriptMgr.h"
#include "SpellAuraEffects.h"
#include "SpellAuras.h"
#include "SpellInfo.h"
#include "StringConvert.h"
#include "Tokenize.h"
#include <unordered_set>

namespace
{
    struct Config
    {
        bool enabled = true;
        bool damage = true;
        bool healing = true;
        bool classSpellsOnly = true;
        std::unordered_set<uint32> useSpellCrit;
        std::unordered_set<uint32> excluded;
    };

    Config config;

    // Spells with no damage class that should still crit, with the caster's spell crit:
    // Lightwell Renew and Frost Fever. The core treats every other spell with no damage class as
    // unable to crit, which is what keeps the next list from double-dipping.
    constexpr char const* DEFAULT_USE_SPELL_CRIT = "7001,55095";

    // Ticks whose amount already comes from a crit or from a heal that could crit. Letting these
    // crit as well would count the same crit twice: Ignite, Deep Wounds, Righteous Vengeance,
    // Sheath of Light, Languish, Piercing Shots, Blessed Recovery, Holy Mending, Glyph of Flash of
    // Light and Glyph of Prayer of Healing.
    constexpr char const* DEFAULT_EXCLUDED = "12654,12721,61840,54203,71023,63468,27813,64891,54957,56161";

    std::unordered_set<uint32> ParseSpellList(std::string const& list)
    {
        std::unordered_set<uint32> spells;
        for (std::string_view token : Acore::Tokenize(list, ',', false))
        {
            // Trim spaces so "7001, 55095" works too.
            while (!token.empty() && token.front() == ' ')
                token.remove_prefix(1);
            while (!token.empty() && token.back() == ' ')
                token.remove_suffix(1);

            if (Optional<uint32> id = Acore::StringTo<uint32>(token))
                spells.insert(*id);
        }
        return spells;
    }

    // Lists hold first ranks, but any rank's own ID matches too.
    bool InList(std::unordered_set<uint32> const& list, SpellInfo const* spellInfo)
    {
        return list.count(spellInfo->Id) || list.count(spellInfo->GetFirstRankSpell()->Id);
    }

    bool IsClassFamily(uint32 family)
    {
        switch (family)
        {
            case SPELLFAMILY_MAGE:
            case SPELLFAMILY_WARRIOR:
            case SPELLFAMILY_WARLOCK:
            case SPELLFAMILY_PRIEST:
            case SPELLFAMILY_DRUID:
            case SPELLFAMILY_ROGUE:
            case SPELLFAMILY_HUNTER:
            case SPELLFAMILY_PALADIN:
            case SPELLFAMILY_SHAMAN:
            case SPELLFAMILY_DEATHKNIGHT:
                return true;
            default:
                return false;
        }
    }

    // The aura types whose ticks roll for a crit in the core.
    bool IsAffectedTick(AuraType type)
    {
        switch (type)
        {
            case SPELL_AURA_PERIODIC_DAMAGE:
            case SPELL_AURA_PERIODIC_LEECH:
                return config.damage;
            case SPELL_AURA_PERIODIC_HEAL:
                return config.healing;
            default:
                return false;
        }
    }

    // The caster's spell crit for the spell's school, for spells with no damage class.
    float SpellCritWithoutDamageClass(Unit const* caster, SpellInfo const* spellInfo)
    {
        // A Lightwell casts Lightwell Renew; the priest's crit counts.
        Player* owner = caster->GetSpellModOwner();
        if (!owner)
            return 0.0f;

        SpellSchoolMask schoolMask = spellInfo->GetSchoolMask();
        float chance = (schoolMask & SPELL_SCHOOL_MASK_NORMAL)
            ? owner->GetFloatValue(PLAYER_CRIT_PERCENTAGE)
            : owner->GetFloatValue(static_cast<uint16>(PLAYER_SPELL_CRIT_PERCENTAGE1) + GetFirstSchoolInMask(schoolMask));

        owner->ApplySpellMod(spellInfo->Id, SPELLMOD_CRITICAL_CHANCE, chance);
        return chance;
    }

    // The same crit chance the caster would have with a direct hit of this spell. target is
    // null for ground effects (Consecration, Flamestrike's burn), as in the core.
    float CalcTickCritChance(Unit const* caster, Unit const* target, SpellInfo const* spellInfo)
    {
        if (spellInfo->DmgClass == SPELL_DAMAGE_CLASS_NONE)
        {
            if (!InList(config.useSpellCrit, spellInfo))
                return 0.0f;

            // The core's target side returns 0 for these, so only resilience applies.
            float chance = SpellCritWithoutDamageClass(caster, spellInfo);
            if (target && !spellInfo->IsPositive())
                Unit::ApplyResilience(target, &chance, nullptr, false, CR_CRIT_TAKEN_SPELL);

            return std::max(0.0f, chance);
        }

        WeaponAttackType attackType = spellInfo->DmgClass == SPELL_DAMAGE_CLASS_RANGED ? RANGED_ATTACK : BASE_ATTACK;
        float chance = caster->SpellDoneCritChance(nullptr, spellInfo, spellInfo->GetSchoolMask(), attackType, true);
        if (chance <= 0.0f)
            return 0.0f;

        // Target side: resilience, crit-taken debuffs, defense skill.
        if (target)
            chance = target->SpellTakenCritChance(caster, spellInfo, spellInfo->GetSchoolMask(), chance, attackType, true);

        return std::max(0.0f, chance);
    }
}

class ForeverPeriodicCritWorldScript : public WorldScript
{
public:
    ForeverPeriodicCritWorldScript() : WorldScript("ForeverPeriodicCritWorldScript", { WORLDHOOK_ON_AFTER_CONFIG_LOAD }) { }

    void OnAfterConfigLoad(bool /*reload*/) override
    {
        config.enabled         = sConfigMgr->GetOption<bool>("ForeverPeriodicCrit.Enable", true);
        config.damage          = sConfigMgr->GetOption<bool>("ForeverPeriodicCrit.Damage", true);
        config.healing         = sConfigMgr->GetOption<bool>("ForeverPeriodicCrit.Healing", true);
        config.classSpellsOnly = sConfigMgr->GetOption<bool>("ForeverPeriodicCrit.ClassSpellsOnly", true);
        config.useSpellCrit    = ParseSpellList(sConfigMgr->GetOption<std::string>("ForeverPeriodicCrit.UseSpellCrit", DEFAULT_USE_SPELL_CRIT));
        config.excluded        = ParseSpellList(sConfigMgr->GetOption<std::string>("ForeverPeriodicCrit.ExcludeSpells", DEFAULT_EXCLUDED));
    }
};

class ForeverPeriodicCritUnitScript : public UnitScript
{
public:
    ForeverPeriodicCritUnitScript() : UnitScript("ForeverPeriodicCritUnitScript", true, { UNITHOOK_ON_AURA_APPLY }) { }

    // The core works out a periodic aura's crit chance when the aura is created and again when
    // it's refreshed or stacked, then calls this hook. Raising the chance here lasts until the
    // next refresh, which calls the hook again.
    void OnAuraApply(Unit* /*unit*/, Aura* aura) override
    {
        if (!config.enabled || !aura)
            return;

        SpellInfo const* spellInfo = aura->GetSpellInfo();
        if (spellInfo->IsPassive() || spellInfo->HasAttribute(SPELL_ATTR2_CANT_CRIT))
            return;

        if (config.classSpellsOnly && !IsClassFamily(spellInfo->SpellFamilyName))
            return;

        if (InList(config.excluded, spellInfo))
            return;

        // Players, their pets and totems. NPC DoTs and HoTs stay as in stock.
        Unit* caster = aura->GetCaster();
        if (!caster || !caster->GetSpellModOwner())
            return;

        Unit* target = aura->GetType() == UNIT_AURA_TYPE ? aura->GetUnitOwner() : nullptr;

        for (uint8 i = 0; i < MAX_SPELL_EFFECTS; ++i)
        {
            AuraEffect* effect = aura->GetEffect(i);
            if (!effect || !IsAffectedTick(effect->GetAuraType()))
                continue;

            // Keep the core's chance when it's higher, e.g. from Shadowform or Pandemic. This also keeps
            // set bonuses that let an excluded spell crit (Righteous Vengeance with Ret T9).
            float chance = CalcTickCritChance(caster, target, spellInfo);
            if (chance > effect->GetCritChance())
                effect->SetCritChance(chance);
        }
    }
};

void AddForeverPeriodicCritScripts()
{
    new ForeverPeriodicCritWorldScript();
    new ForeverPeriodicCritUnitScript();
}
