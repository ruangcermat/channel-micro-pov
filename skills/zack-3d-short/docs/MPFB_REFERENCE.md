# MPFB2 reference: the exact names (dumped from our real characters on 2026-11-22)

Use these names exactly. A wrong bone or key name fails silently: nothing moves.

## Objects that one MPFB human creates

The objects below are from `ready/family_ready.blend`. Every part is parented to the rig.

```
Mom_rig [ARMATURE]                 <- move / rotate the whole person with this
  Mom_body [MESH]                  <- skin; carries ALL shape keys (body + face)
  Human.long01                     hair
  Human.eyebrow010                 eyebrows
  Human.eyelashes01                lashes
  Human.high-poly                  eyes (follow eye.L / eye.R bones)
  Human.teeth_base                 teeth   (follow the JAW BONE, not shape keys)
  Human.tongue01                   tongue  (follows the jaw bone and the tongue bones)
  Human.female_casualsuit01        clothes
  Human.shoes06                    shoes
  Mom_TearL / Mom_TearR [CURVE]    our tear streaks (grow with bevel_factor_end)
  Mom_LidL / Mom_LidR [CURVE]      our wet lower-lid line (shown when crying)
```

The kid is the same, with `Kid_` names and `.001` copies of the shared parts (`Human.teeth_base.001`…).

**Rule:** if an object is NOT parented to the rig, it floats away when the body moves. Check with:

```python
[o.name for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith('Human.') and not o.parent]
```

## Bones (163, the "default" rig, the same for every human)

| Body part | Bones |
|---|---|
| root, hips | `root`, `pelvis.L/R` |
| legs | `upperleg01.L/R`, `upperleg02.L/R`, `lowerleg01.L/R`, `lowerleg02.L/R`, `foot.L/R`, toes `toe1-1.L` … `toe5-3.R` |
| spine | `spine05` (lowest) `spine04` `spine03` `spine02` `spine01` (chest), plus `breast.L/R` |
| neck, head | `neck01` `neck02` `neck03` `head` |
| arms | `clavicle.L/R`, `shoulder01.L/R`, `upperarm01.L/R`, `upperarm02.L/R`, `lowerarm01.L/R`, `lowerarm02.L/R`, `wrist.L/R` |
| fingers | `finger1-1..3` (thumb) … `finger5-1..3` (pinky), `.L/.R`, plus `metacarpal1-4.L/R` |
| jaw | **`jaw`**: rotate it to open the mouth (the teeth and tongue go with it) |
| eyes | `eye.L`, `eye.R` (aim them for eye direction), `orbicularis03/04.L/R` (lids) |
| face detail | `oris01-07`, `levator02-06`, `risorius02/03`, `temporalis01/02`, `oculi01/02`, `special01-06`, `tongue00-07` |

**How we pose:**

- **Legs:**
  - IK on `lowerleg02.X`: chain 4, `use_tail=True`, target = an empty at the ankle, pole = an empty in front of the knee.
  - Feet: COPY_ROTATION from an empty in world space.
- **Arms:** `reach(arm, side, world_target, pole)` in kitchen_shots.py. It's an analytic 2-bone solve plus 3 CCD passes, and is exact to about 1 mm.
- **Everything else:** `doc_pose.rot_world(arm, posebone, world_axis, degrees)`. It rotates around a WORLD axis, so you don't have to think about bone rolls.
- **Rest pose:** always reset `pb.matrix_basis.identity()` for every posed bone at the start of each frame, then rebuild the pose. Then key it. This avoids drift.

## Shape keys on `<Name>_body`

| Prefix | What it is | Rule |
|---|---|---|
| `Basis` | rest mesh | never touch |
| `$md-…` | **the BODY** (gender, age, weight, proportions…), 7 on the kid, 21 on the mom | **NEVER set these to 0.** If you do, the body vanishes and only the clothes are left. |
| `head-oval`, `r-eye-scale-incr`… | face sculpt targets from `make()` | fine to adjust 0..1 |
| `!ex-<ARKit name>` | **face expression units** | the only keys you animate |

**Face units loaded on our characters:** MPFB only creates the units you touch at build time. These are the 31 we touched:

```
mouthSmileLeft/Right  cheekSquintLeft/Right  eyeSquintLeft/Right  browOuterUpLeft/Right
jawOpen  eyeWideLeft/Right  browInnerUp  mouthFunnel  mouthStretchLeft/Right
mouthFrownLeft/Right  mouthLowerDownLeft/Right  mouthPressLeft/Right
eyeLookDownLeft/Right  mouthRollLower  browDownLeft/Right  noseSneerLeft/Right
jawForward  eyeBlinkLeft/Right
```

**Need another unit?** Add it to the dict passed to `FaceService.set_expression(body, {...: 0.01})` in `make()` and rebuild the character. The full ARKit set of 52 (faceunits01 has all of them):

```
browDownLeft browDownRight browInnerUp browOuterUpLeft browOuterUpRight
cheekPuff cheekSquintLeft cheekSquintRight
eyeBlinkLeft eyeBlinkRight eyeLookDownLeft eyeLookDownRight eyeLookInLeft eyeLookInRight
eyeLookOutLeft eyeLookOutRight eyeLookUpLeft eyeLookUpRight eyeSquintLeft eyeSquintRight eyeWideLeft eyeWideRight
jawForward jawLeft jawOpen jawRight
mouthClose mouthDimpleLeft mouthDimpleRight mouthFrownLeft mouthFrownRight mouthFunnel mouthLeft
mouthLowerDownLeft mouthLowerDownRight mouthPressLeft mouthPressRight mouthPucker mouthRight
mouthRollLower mouthRollUpper mouthShrugLower mouthShrugUpper mouthSmileLeft mouthSmileRight
mouthStretchLeft mouthStretchRight mouthUpperUpLeft mouthUpperUpRight noseSneerLeft noseSneerRight tongueOut
```

Useful extras for Zack-style faces:
- `cheekPuff`: holding breath, disgust
- `mouthPucker`: "ooh", kiss
- `eyeLookUp*`: thinking
- `mouthShrugUpper`: doubt
- `mouthDimple*`: a smug smile

## Expression recipes (multiply by BOOST 1.6, clamp to 1)

`sym(x_=v)` sets both `xLeft` and `xRight`.

| Name | Units |
|---|---|
| neutral | mouthSmile_ .12 |
| happy | mouthSmile_ .75, cheekSquint_ .45, eyeSquint_ .25, browOuterUp_ .2, jawOpen .12 |
| laugh | mouthSmile_ .62, cheekSquint_ .6, eyeSquint_ .55, browOuterUp_ .3, browInnerUp .2, jawOpen .4, mouthLowerDown_ .3 (plus a head bounce `abs(sin(t*8.5))`) |
| shock | eyeWide_ .9, browInnerUp .9, browOuterUp_ .8, jawOpen .55, mouthFunnel .25 |
| panic | eyeWide_ .8, browInnerUp 1, mouthStretch_ .6, mouthFrown_ .4, jawOpen .2, mouthLowerDown_ .4 |
| guilty | browInnerUp .7, mouthFrown_ .5, mouthPress_ .45, eyeLookDown_ .55, mouthRollLower .3, mouthStretch_ .2 |
| crying | browInnerUp 1, browDown_ .15, eyeSquint_ .7, mouthFrown_ .8, mouthStretch_ .35, cheekSquint_ .5, jawOpen .18, mouthLowerDown_ .35, noseSneer_ .3 (plus tears) |
| sting (onion eyes) | eyeSquint_ .9, browDown_ .5, browInnerUp .5, noseSneer_ .5, cheekSquint_ .6, mouthFrown_ .3 |
| angry | browDown_ .85, eyeSquint_ .4, eyeWide_ .25, noseSneer_ .75, mouthPress_ .5, mouthFrown_ .55, mouthStretch_ .35, jawForward .2 |
| relieved | mouthSmile_ .5, browInnerUp .35, cheekSquint_ .2 |

To see what each one looks like, open `reference/expressions/` (mom and kid, each expression).

## Talking and the mouth

- `jaw = min(1, jawOpen_value + talk*0.35)`, where `talk` is the voice loudness for that frame (RMS of vo.wav, normalised to the 95th percentile).
- **Jaw bone:** rotate it `17° * jaw` around the head's left axis (`D.rot_world(arm, P["jaw"], left, 17*jaw)`).
- **Shape key:** set `!ex-jawOpen = jaw * 0.25` (the bone does most of the opening; the key only shapes the lips).
- Add `mouthFunnel += talk*0.15` for vowel shapes.
- **Teeth material:** MPFB's default renders dark grey.
  - Link the teeth image texture directly to Base Color.
  - Set Roughness 0.28, Coat 0.3, Subsurface 0.15.
  - Never use a flat colour: that turns the gums grey (see `reference/BAD_grey_teeth_before_fix.jpg` vs `GOOD_teeth_after_fix.jpg`).

## Blinks

- Random every 2.0-3.6 s, with a different seed per character.
- 9-frame curve: `[0, .35, .8, 1, 1, .8, .5, .2, 0]` on `eyeBlinkLeft/Right`, taking the max with the expression's own value.

## Tears (family.py `add_tears`)

- Start at the inner lower lid.
- Raycast down the cheek every ~4 mm, offset 0.6 mm off the skin, to build the curve points.
- Bevel depth 0.0021 m, round.
- Material: Transmission 1, IOR 1.33, Roughness 0.05, plus a little Coat.
- Animate `bevel_factor_end` from 0.02 to 1.0 to make the tear run down.
- Turn on `hide_render` when the amount is 0 (don't scale to 0).
- Check it at an 85 mm close-up: the tear must catch a highlight. If you can't see it, add a small rim light from behind.

## Phenotype cheat sheet (`info["phenotype"]`)

| Key | 0 | 0.5 | 1 |
|---|---|---|---|
| gender | female | in between | male |
| age | baby | 25 y | 90 y. Kid about 10 y = **0.16**, teen = 0.3, parent of about 35 = **0.6**, grandparent = 0.85 |
| weight | thin | average | heavy |
| muscle | soft | average | muscular |
| height | short | average | tall |
| proportions | stylised | | idealised |
| cupsize, firmness | | | (female only) |
| race | a dict of caucasian, african and asian weights that sum to 1 | | |

Each skin's texture should match the race and age. Skin options: young/middleage/old × caucasian/african/asian × male/female.
