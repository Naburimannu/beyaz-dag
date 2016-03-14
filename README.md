# Beyaz Dag

It is not far from Navekat and Suyab to the lake they call the Eye of the World. But the visions you sought there carried you much farther,
across mountains, deserts, marshes, across the Mother River to the lonely Mount Beyaz. Here, perhaps, you can convince the merciful goddess
who lives above the clouds to save your people from the plague.

Beyaz Dag towers solitary above the deserts. No rival peak dares rear itself nearby, though a desultory range of hills stretches southwards. The mountain’s western slopes fall off steeply into a deep blue lake; north lie the marshes that fringe the Mother River.

You never mastered sword and lance, like your brothers, but can shoot, ride, and wrestle as well as any of them.

Beyaz Dag teems with life: hyenas and gazelles in the desert scrub, deer, wolves, bear in the forests. Travelers you met on the Northern Road tell of other, darker things here: ruins, abandoned quarries, sunken grottoes...


Now you're almost through the marshes; the mountain rises to the southwest.


* Source at https://github.com/Naburimannu/beyaz-dag
* Engine at https://github.com/Naburimannu/libtcodpy-tutorial

Originally based on Jotaf's Python roguelike tutorial for libtcod.


## Combat Model

If you are unfortunate enough to get into a fight, you'll see messages in your log like:

> Player (40) attacks hyena (10) for 4 wounds.
> Hyena (16) attacks player (20) but misses.

The numbers in parentheses are the participants' effective attack and defense skills. Equal skills provide a 50% chance of success; a 2:1 ratio in skills provides a 75% chance of success, a 3:1 ratio an 85% chance of success. All attack success chances depend on the weapon used; melee defense depends on shield skill if a shield is equipped, plus half of weapon skill. Missile defense depends on the distance between the combatants, plus half of shield skill if a shield is equipped.

All effective skills are reduced by: exhaustion, wounds, bleeding, intoxication.
Exhaustion accumulates as you walk, climb, or fight; it can be reduced by food and drink.
Wounds accumulate from combat; if wounds ever exceed your maximum hit points (36), you fall unconscious - and since you have no companions it's assumed you die.
Bleeding sometimes occurs during combat; once you're bleeding, you'll continuously lose hit points until they reach 0 and you die. First aid skill and the application of bandages are necessary to stop bleeding.
Intoxication is a side effect of some beverages or other events in the world.

Based on Wizard's Crown and related games published for personal computers in the mid-1980s.

## Strategy Notes

* Fighting is dangerous and rarely beneficial.
** Archery is deadly, but arrows are in short supply.
** If you get out of sight of your enemies, they're not likely to pursue very far.
* Melee weapon skills also influence defense.
** To be effective, have a skill of at least 40 in any weapon you use.
* Choices are hard.
** Fighting the wrong enemy without a shield (and shield skill) may be fatal.
** Fighting the wrong enemy in melee instead of with a bow may be fatal.
** Switching between bow and shield at a bad time may be fatal.

## Spoilers

* Grinding can yield more than 400 skill points, but a successful playthrough may only need half that.
* AI pathing is really, really poor; (in the current build) you are expected to exploit this.


