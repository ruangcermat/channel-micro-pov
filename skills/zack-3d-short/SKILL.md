---
name: zack-3d-short
description: Make a realistic Zack D Films-style 3D story short in real Blender (no AI video, no paid tools) - MPFB2 humans (mom, kid, any age/body), facial expressions (ARKit face keys), teeth/jaw talking, tears, painted T-shirt logos, rooms built from Poly Haven scans plus code (kitchen, living room, street view through the window), props in hands (knife, onion), gas/smoke, 15-shot story timeline synced to a Gemini Fenrir voice, captions and quality checks. Use when the user asks for a Zack-style / realistic 3D short, "like the onion / mom crying video", new characters, changing a character/set/expression, or matching Zack's quality.
---

# Zack-style realistic 3D short (Blender + MPFB2)

## STEP 0: ask first (always, before any work)

When this skill starts, ask the user these 3 questions in ONE message (use AskUserQuestion if it's available) and wait for the answers:

1. **Niche:** what is the channel or video about? (e.g. science facts, history, "what if", life lessons, horror, kids stories)
2. **Length:** how long? (15 s, 30 s, 60 s, or longer)
3. **Script:** do you already have a script?
   - **Yes:** ask them to paste it. Use it word for word; only add "!" and CAPS for the hype voice, and tell them if anything was changed.
   - **No:** find 5 ideas in that niche (web search Zack D Films-style topics), let them pick one, then write the script in our own words to fit the length (about 2.7 words per second; 30 s ≈ 80 words). Show it and wait for approval before building anything.

Only after these answers: plan the characters, set and shots to fit the niche and length.

Proven on the 31.5 s "Mom was crying" onion short (Nov 2026). See `example/test_shots.jpg` for all 15 shots and `example/voice/` for the script, voice and word times.

- Walking, turning and sitting example: the **blender-walk-example** skill.
- Rendering (Colab, Kaggle, PC, EEVEE) and finishing the MP4: the **blender-render-farm** skill.
- The study notes from Mr Omi's Zack-method video: `METHOD.md`. Read it once.

## What's in this skill (read these before building)

| File | Use it for |
|---|---|
| `docs/WALKTHROUGH_ONION_SHORT.md` | **Read first.** The whole video step by step: script, voice, shot table, checks, timings. Copy this order. |
| `docs/MPFB_REFERENCE.md` | Exact bone names, face-key names (all 52), expression recipes, jaw/teeth/tears/blink settings, phenotype cheat sheet. |
| `docs/SCRIPTS.md` | What every script does, its arguments, the data flow, and the helper functions to reuse. |
| `docs/TROUBLESHOOTING.md` | Every bug we hit and its fix. Check it before showing any frame. |
| `ready/family_ready.blend` | **Ready-made mom and kid**, every texture packed. Open it and skip the character build. Preview: `ready/family_ready_preview.jpg`. |
| `reference/` | What GOOD looks like: expressions for both characters, characters, tears, sets, window view, all 15 final shots, and bad vs good teeth. Compare your renders to these. |
| `example/voice/` | The real script, voice, and word timings of the onion short. |
| `METHOD.md` | Notes on how Zack's videos are measured and made (camera, sets, look, sound, speed). |

**Fastest start:** `blender -b ready/family_ready.blend -P scripts/kitchen_set.py -- renders/test.png 16 360`
- This was tested and works: it builds the kitchen around the ready-made mom and kid.
- MPFB is only needed to make NEW characters or change the existing ones' bodies, hair or clothes.

## Pipeline (one .blend per stage, every script is re-runnable)

```
paint_family.py  -> tex/*_tee_diffuse.png        (system python: PIL + numpy)
family.py        -> renders/family.blend         (characters + expression test renders)
make_kitchen_tex.py -> tex/calendar.png, drawing.png
kitchen_set.py   -> renders/kitchen.blend        (set + street.py view through the window)
living_room.py   -> renders/kitchen.blend        (adds 2nd room at x+12: sofa, TV, backpack)
kitchen_shots.py -> renders/kitchen_anim.blend   (every frame keyed: cameras, bodies, faces, props)
fix_*.py         -> patches on the baked file    (cheaper than re-baking)
render           -> blender-render-farm skill
```

Run each Blender script as `blender -b <in.blend> -P script.py -- <out|none> <samples> <width> [frames]`.

- Test frames: 360-540 px, 12-20 samples, 1 frame per shot, all put together in one contact sheet.
- Each stage needs the folders `assets/` (Poly Haven), `tex/` and `renders/` next to the scripts.
- Get the models with `python fetch_polyhaven.py <models,...> <textures,...>`. `polyhaven_assets.txt` lists every asset we have used.

## 1. Characters: MPFB2 (MakeHuman for Blender, CC0, no account)

### Where the characters come from (exactly how we got them)

We DON'T download finished characters, and we DON'T use AI or paid models.
- Every person is BUILT inside Blender with **MPFB2**, the free MakeHuman add-on, from free CC0 parts: body, skin, eyes, teeth, hair, clothes.
- Avoid scanned people and MetaHuman: scans can't act (no face rig), and MetaHuman needs an account and a token.

**One-time setup (about 10 minutes; Claude can run all of it):**

```bash
B="C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"   # Mac: /Applications/Blender.app/Contents/MacOS/Blender

# 1. Install MPFB2 from Blender's official extension site (free, no account)
"$B" -c extension install -s -e mpfb
#    (or by hand: Blender -> Edit -> Preferences -> Get Extensions -> search "MPFB" -> Install)

# 2. Download the 2 free asset packs (CC0)
mkdir -p mpfb_pack
curl -L -o mpfb_pack/makehuman_system_assets_cc0.zip http://files.makehumancommunity.org/asset_packs/makehuman_system_assets/makehuman_system_assets_cc0.zip
curl -L -o mpfb_pack/faceunits01.zip https://files.makehumancommunity.org/functional/faceunits01.zip
#    system assets = skins, hair, eyebrows, eyes, teeth, tongue, clothes, shoes
#    faceunits01   = the 52 ARKit face keys (iPhone face-capture set). WITHOUT IT THERE ARE NO EXPRESSIONS.

# 3. Load both packs into MPFB
"$B" -b -P scripts/mpfb_loadpack.py -- mpfb_pack/makehuman_system_assets_cc0.zip
"$B" -b -P scripts/mpfb_loadpack.py -- mpfb_pack/faceunits01.zip
```

- If a link is dead, find the current one on http://static.makehumancommunity.org/assets/assetpacks.html
- **Check it worked:** the MPFB data folder must now have `skins/ hair/ clothes/ eyebrows/ eyes/ teeth/ packs/`.
  - Windows: `%APPDATA%/Blender Foundation/Blender/5.2/extensions/.user/blender_org/mpfb/data/`
  - Mac: `~/Library/Application Support/Blender/5.2/extensions/.user/blender_org/mpfb/data/`
  - Linux: `~/.config/blender/5.2/extensions/.user/blender_org/mpfb/data/`
- **Then test it:** run `family.py` with the `pair` view. You should see a mom and a kid with bodies, clothes and faces.

**Picking the look:** the folder names in that data folder ARE the names to put in `make()`.
- Hair: `long01`, `short01`, `bob02`, `ponytail01`
- Clothes: `female_casualsuit01`, `male_casualsuit06`
- Shoes: `shoes05`, `shoes06`
- Skins: `young_caucasian_female`, `middleage_african_male`
- Eyebrows: `eyebrow010`
- List them all with `ls <data>/hair` and so on. What the system pack contains (checked on 2026-11-22):
  - **hair:** afro01 bob01 bob02 braid01 long01 ponytail01 short01 short02 short03 short04
  - **skins:** {young, middleage, old} × {caucasian, african, asian} × {male, female}, plus young_caucasian_female2, young_caucasian_male2 and toon01
  - **clothes:**
    - female_casualsuit01/02, female_elegantsuit01, female_sportsuit01
    - male_casualsuit01-06, male_elegantsuit01, male_worksuit01
    - fedora01, fedora_cocked
    - shoes01-06
  - **eyebrows:** eyebrow001-012

**New character recipe:**
1. Copy a `make()` call in `family.py`.
2. Change the phenotype (gender, age, weight, race mix), the hair, clothes, skin and eyebrows.
3. Render the `<name>_neutral` and `<name>_shock` views and zoom in on the face.
4. Repaint the clothes or add text with `paint_family.py`.
5. Give every character a different silhouette (age, height, hair, clothes colour) so viewers tell them apart at a glance.

**Building a person** (`family.py` → `make()`):

- `HumanService._create_default_human_info_dict()`, then set:
  - `phenotype`:
    - gender: 0 = female, 1 = male
    - age: 0.16 = about a 10-year-old, 0.5 = 25, 0.6 = about 35
    - weight, muscle, height, proportions, cupsize
    - race mix
  - `targets`: face sculpt, e.g. head-oval, eye-scale, cheek-bones.
  - Assets: `eyes` high-poly, `eyebrows`, `eyelashes`, `teeth_base`, `tongue01`, `hair` (long01, short01…), and `clothes` (e.g. female_casualsuit01, male_casualsuit06, shoes05/06).
  - `skin_mhmat` (e.g. young_caucasian_female) and `skin_material_type = "ENHANCED_SSS"` (stops the waxy look).
  - `rig = "default"`.
- `HumanService.deserialize_from_dict(info, settings)` with `settings["scale"] = 0.1` (metres).
- To list what's available, look in `%APPDATA%/Blender Foundation/Blender/5.2/extensions/.user/blender_org/mpfb/data/{hair,clothes,skins,eyebrows}`.

**Rules (each one was a real bug):**

- **NEVER zero the `$md-…` shape keys.** They ARE the body. Zeroing them left "just clothes, no body". Touch only keys starting with `!ex-`.
- **Load the face keys** by calling `FaceService.set_expression(body, {all keys: 0.01})` once at build time.
- **Clothes:**
  - Add a Displace modifier (0.006) on the clothes, or socks and skin poke through.
  - Always relax the arms with `doc_pose.pose_arms` / `relaxed_hands`. Never leave the A-pose.
- **Eyes, teeth, hair and clothes must follow the armature.** If something floats off the body, it isn't parented.

**Painting clothes (T-shirt logo "MR UDO", colours):** `paint_family.py`

1. Rasterise the garment's UV mask from its `.obj`.
2. Recolour the diffuse texture inside the mask (e.g. red tee, sage green tee).
3. Patch out the stock logo.
4. Draw the text in Arial Black at a UV spot (tx/ty/tw). Check it at 1:1 on the chest in a front render. The text must not be mirrored or cut by a seam.

## 2. Expressions, talking, tears, eyes

- **Expressions** are dicts of ARKit units (in `family.py` `EXPR` and `kitchen_shots.py`). `sym()` mirrors the `_` keys to Left/Right.

  ```
  happy  : mouthSmile .75, cheekSquint .45, eyeSquint .25, browOuterUp .2, jawOpen .12
  shock  : eyeWide .9, browInnerUp .9, browOuterUp .8, jawOpen .55, mouthFunnel .25
  panic  : eyeWide .8, browInnerUp 1, mouthStretch .6, mouthFrown .4, jawOpen .2, mouthLowerDown .4
  guilty : browInnerUp .7, mouthFrown .5, mouthPress .45, eyeLookDown .55, mouthRollLower .3
  crying : browInnerUp 1, eyeSquint .7, mouthFrown .8, mouthStretch .35, cheekSquint .5, jawOpen .18, noseSneer .3
  angry  : browDown .65, eyeSquint .35, noseSneer .6, mouthPress .4, mouthFrown .4, jawForward .15
  relieved: mouthSmile .45, browInnerUp .35, eyeBlink .35
  ```

  - Multiply by `BOOST = 1.6`. Zack faces are BIG and readable on a phone.
  - New emotion: combine units, render the `kid_<expr>` / `mom_<expr>` views, and zoom in before using it.
- **Blend between expressions** over 6-10 frames (`set_face(body, t, e1, e2, k)`). Never snap.
- **Blinks:** random every 2-5 s, 4-frame close/open. Faces without blinks look dead.
- **Talking / jaw:**
  - The teeth and tongue are proxies that follow the `jaw` BONE, not shape keys.
  - So drive the jaw bone (`rot_world(arm, jaw, left, 17*jaw)`) from the voice loudness, plus `jawOpen` at 0.25×.
  - Using only the jawOpen key leaves the teeth floating shut.
- **Teeth colour:** keep the teeth texture linked to Base Color. A flat ivory turned the gums grey.
- **Tears** (`family.py`):
  - Curves projected onto the cheek by raycasting from the inner eye corner down.
  - bevel 0.0021, glassy material (transmission, IOR 1.33, low roughness), parented to the head bone.
  - Animate them growing with `bevel_factor_end` from 0 to 1.
  - Viewers must SEE water on the face: check it in a close-up.

## 3. Sets (real assets first, code for the rest)

- **Rule from METHOD.md:** if a real scan exists, download it (Poly Haven CC0). Hand-built furniture looks like "AI slop".
  - Code-build only simple boxes: cabinets, counters, walls, the fridge, the TV.
- **Kitchen** (`kitchen_set.py`):
  - Room X -2.3..2.3, Y -2.6..1.8, ceiling 2.6.
  - Textured floor and walls (`tex_mat`), marble worktop, subway tiles (Brick texture node).
  - Stove, sink, fridge, a window and a door.
  - 12-20 readable story props: board, onions, knife, food, kettle, toaster, microwave, cereal, calendar, kid's drawing, towel, table and chairs, backpack, pendant lamp.
- **Window view** (`street.py` `build()`): grass, pavement, road with dashes, picket fence, a row of houses with roofs, windows and doors, trees, a car, a street lamp, and a sky card 40 m out.
  - "Make the window feel alive" = a real street, not a flat colour.
  - Keep trees off the window line.
- **Second room** (`living_room.py`): appends `doc_room.blend` (from blender-walk-example) at x+12, without Doc.
  - Front wall, TV (frame plus emissive screen showing a cartoon), TV glow light, backpack with the F test, remote.
  - Raycast the sofa seat height for sitting.
- **TV picture:**
  - Use N images switched by keyed Mix nodes (`fix_tv.py`), NOT an image sequence. Sequences can't be packed for cloud rendering.
- **Hand-held props** (e.g. the knife is an empty with blade, handle and rivets):
  - Every frame, place the prop from the hand: `wrist.head + palm_dir*0.055 + up*0.045`.
  - Reach the hand to world targets with `reach()` (two-bone solve plus CCD).
  - Check for floating knives and onions in EVERY shot that shows them.
- **Gas / smoke:** volumetric ico-sphere puffs (Principled Volume, 4D noise, density about 170) rising from the cut onion toward the eyes.
  - **Never scale a puff to ~0.** Cycles crashes silently. Key `hide_render` instead (`fix_gas.py`).
  - The puffs must start at the board and drift, not fly around like props.

## 4. Story, shots, camera (`kitchen_shots.py`)

- **Story:**
  - Hook in the first second.
  - Misunderstanding, then confession, then a science explainer, then a twist ending.
  - Find ideas on the web (Zack D Films topics); write our own words.
- **Script:**
  - Write the voice first.
  - Get the word times with Whisper on a 16 kHz wav (`words.json`).
  - Then define `SHOTS = [(start_s, "name"), …]`. Each cut lands on a word.
  - The onion short has 15 shots in 31.5 s: about 2 s each, a new framing on every beat.
- **Camera (measured on Zack):**
  - One eased dolly or push-in per shot. Zero sideways pan, no orbit drift, no shake.
  - Depth of field (f/2.8) on close-ups. Focus on the eyes.
- **Character placement:**
  - Keep characters in frame together for two-shots: they were 1.8 m apart. Pull the camera back with a wider lens (24 mm).
  - Keep characters where the story says they are: the kid must not appear in the kitchen while he's still on the sofa.
- **Debug:** check for a camera inside an object (the toaster made a black frame). Raycast from the camera to the target.

## 5. Voice and captions

- **Voice:** Gemini TTS, Fenrir, hype style, CAPS and "!" in the script:
  `tts_gemini.py vo.txt vo.mp3 --whole --voice Fenrir --model gemini-3.8-flash-tts --style "..."`.
  - The model READS THE STYLE PREFIX aloud. Transcribe the output and cut before the first script word with `ffmpeg -ss`.
  - The free tier allows about 10 requests a day per model. Don't burn retries.
- **Word times:** convert to a 16 kHz wav first (`av.open` fails on mp3), then run faster-whisper with word timestamps.
- **Captions:** `video-editor/scripts/captions.py VIDEO transcript.json OUT --words 3 --upper`.

## 6. Matching Zack's quality (the checklist before any full render)

1. **Render one frame per shot** at 360-540 px into one contact sheet. Zoom on:
   - faces (expression readable? teeth correct? tears visible?)
   - hands (props gripped, not floating)
   - feet (not sinking)
   - text (MR UDO readable, not mirrored)
   - window (street visible)
2. **Lighting:**
   - A motivated key light (window or sun) with warm/cool contrast.
   - No muddy midtones. Keep the subject brighter than the background.
3. **Skin:** SSS on and matte, not waxy. Hair must not clip.
4. **Camera look:** `post.py` (soft lens, glow, vignette, grain), and motion blur on fast moves.
5. **Measure ours against Zack's:** camera jerk and words/s (about 2.77 calm; we use hype energy). The difference is the to-do list.
6. **Fix everything you can see before showing the user.** Don't send a "weak spots" list.

## Known slow spot (unsolved)

The close-up shots (cut, gas and flood, frames about 520-776) rendered at about 50 s/frame on a T4, versus 11 s elsewhere.
- **Not** caused by the gas, DOF, street or tears.
- **Next:** bisect the hidden object groups, and try per-shot `hide_render` of off-camera sets plus lower volume step rate.
- **Or:** render with EEVEE (blender-render-farm).
