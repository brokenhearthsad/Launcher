# Bot AI

Each of the ten participants is a `BotBrain` (`backend/app/ai/bot.py`) with its own profile, memory and
RNG. Each team also has a `TeamAI` coordinator. Architecture: **Utility AI** — subsystems propose
scored candidate actions, a decision engine weighs them by personality and picks the best. Nothing is a
scripted sequence: choices depend on the current perceived state.

## Decision loop (per bot, every reaction interval)

1. **Perceive** — `adapter.get_player_state()` returns a fog-of-war filtered `Perception`
   (own hero, allies, *visible* enemies, nearby creeps, towers, camps, Roshan, wards, ability readiness).
2. **Analyse** — `CombatAI.assess` builds a threat assessment (ally vs enemy fight power, tower threat,
   incoming burst); retreat check.
3. **Generate** candidates from subsystems.
4. **Evaluate** — `DecisionEngine`: `score × source_weight(personality) + hysteresis − failure_penalty + noise(difficulty)`.
5. **Choose** the best *main* action and, separately, the best *shopping* action (buying does not
   interrupt what the hero is doing).
6. **Execute** via `adapter.execute_action()`.
7. **Observe** the `ActionResult`; failed actions are suppressed for 4 s, purchases/wards recorded.
8. **Update** memory (last intent, HP trend, intent statistics, lane override).

## Subsystems (`backend/app/ai/`)

| Module | Responsibilities |
|--------|------------------|
| `lane.py` — Lane AI | lane assignment by role (safe/mid/off), lane choice after laning (farm vs danger vs travel), holding position behind the creep front, ranged/timid bots stand further back, never idle under an enemy tower without creeps, lane switch when the lane is lost |
| `farming.py` — Farming AI | creep damage estimation with difficulty-dependent error, predicted creep HP (incoming creep damage), timed last hits (`hp_threshold`), denies (<50% HP), supports yield last hits to cores, wave clearing, AoE farming, jungle camp selection by kill time / damage taken / safety |
| `economy.py` — Economy AI | income tracking, reserve for TP scroll, consumable needs (salve, wards), buys next build item when affordable, sells cheap items to make room |
| `items.py` — Item AI | role starting items + core builds, situational adjustments (BKB vs many disables, armor/evasion vs physical, Pipe/Glimmer vs magic, Mekansm if team lacks heals), availability checks, active item usage (salve, clarity, wand, BKB, blink/force escape, Mekansm, Pipe, Glimmer save, Arcane Boots, Satanic, Shiva's, wards) |
| `combat.py` — Combat AI | threat assessment, retreat rules (HP threshold from risk tolerance, lethal burst, outnumbered, tower), target selection (kill potential with allies, HP, role priority, distance, dive penalty, spell immunity), ability usage (stuns not on stunned targets, ultimates only for kills or multi-hits), harassment, heals/shields on allies, rotating to help allies |
| `objective.py` — Objective AI | attack vulnerable towers/ancient when creeps tank or enough allies, defend structures (incl. teleport), Roshan when the team decides |
| `team.py` — Team AI | every 3 s: evaluate alive counts, net worth, power (unseen enemies estimated); directives `farm`, `defend`, `regroup`, `push`, `roshan`, `group` with rally point and participants; greedy carries may skip grouping |
| `decision.py` — Decision Engine | weighting, hysteresis, failure suppression, noise, two channels |

## How settings change behaviour

| Setting | Effect |
|---------|--------|
| Aggression | combat weight `0.7+0.6a`; engage radius in lane; willingness to fight; harass utility |
| Farming priority | farming weight `0.7+0.6f`; last-hit utility; early jungling for cores |
| Team coordination | team-directive weight `0.5+0.8c`; heal/shield/save utility; ally support in kill potential; push threshold of the team |
| Risk tolerance | retreat HP threshold `0.22+0.28(1−r)`; lethal-risk tolerance; tower-dive penalty; lane back-off |
| Objective priority | objective weight `0.7+0.6o` for tower attack/defence/Roshan |
| Difficulty | reaction time (easy 1.5 s, medium 1.0 s, hard/expert 0.5 s), decision noise (0.12 → 0.012), last-hit misjudgement (30% → 2%), chance to use abilities (55% → 100%), creep-damage prediction (hard+) |
| Scenario `aggressive` / `defensive` | +/− aggression and risk for every bot in the session |

Profiles are snapshotted when a session starts, so editing bots never changes a running match.
Tests prove the effect: `tests/test_ai.py::test_decision_engine_weights_personality`,
`tests/test_simulator.py::test_bot_settings_change_behaviour`.

## Inspecting decisions

The Live Match page shows each bot's last action, the subsystem (`source`), utility score and reason;
the Team AI card shows current directives. Per-bot intent counters appear in the live snapshot (`bots`).

## Known limitations

Economy levels are lower than in real Dota 2 (simplified items, no recipes, no talents, abstract map).
Abilities are generic archetype kits, not exact hero kits. Tuning constants live in `catalog.py`,
`engine.py` and the subsystem modules.
