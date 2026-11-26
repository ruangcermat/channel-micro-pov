---
name: blender-walk-example
description: Worked example of a realistic Zack D Films-style 3D clip made in real Blender with an MPFB2 human ("Doc") - a 3 s walk with planted feet, and a living-room walk -> turn -> sit clip. Use when the user says "like the walk video", "like the Doc walk / sit clip", wants a character to walk, turn, sit or move in Blender, or needs a working reference for IK legs, foot planting, arm swing, blinks and a dolly camera.
---

# Blender walk example (the "Doc" clips)

## STEP 0: ask first (always, before any work)

When this skill starts, ask the user these 3 questions in ONE message (use AskUserQuestion if it's available) and wait for the answers:

1. **Niche:** what is the channel or video about? (e.g. science facts, history, "what if", life lessons, horror, kids stories)
2. **Length:** how long? (a 3 s walk test, 15 s, 30 s, 60 s, or longer)
3. **Script:** do you already have a script?
   - **Yes:** ask them to paste it, and plan the walking, turning and sitting moves around its words.
   - **No:** suggest 3 short ideas in that niche where a character walks, turns or sits, let them pick one, then write the script in our own words to fit the length (about 2.7 words per second). Show it and wait for approval before building anything.

Only after these answers: plan the character, room and moves.

This is our proven, approved example. Copy it, then change it. Don't start from zero.

- `example/doc_walk_3s.mp4`: the 3 s walk on the blue studio floor.
- `example/doc_room_sit_720_v2.mp4`: the walk in, turn, and sit in the living room (approved after a frame-by-frame fix pass).
- `example/walk_check_sheet.png`: the contact sheet used to check every frame for foot slide.

Characters, expressions, sets, voice and quality rules are in the **zack-3d-short** skill.
Rendering on Colab, Kaggle or the PC is in the **blender-render-farm** skill.

## Files (copy `scripts/*` into a new project folder)

The scripts expect this layout next to them:

```
project/
  scripts...            (all .py from scripts/)
  assets/               Poly Haven models (fetch_polyhaven.py fills it)
  tex/                  painted clothes textures (paint_hoodie.py writes them; copies are in tex/)
  renders/              .blend files and test PNGs
```

| Script | What it does |
|---|---|
| `mpfb_loadpack.py` | One-time job: enables MPFB2 and loads an asset-pack zip (see zack-3d-short for the setup). |
| `paint_hoodie.py` | System Python with PIL, numpy and scipy. Repaints MPFB `male_casualsuit02` into a navy zip hoodie and black jeans, and flattens the collar normal map. |
| `mpfb_doc.py` | Builds Doc with MPFB2 (body, skin with SSS, eyes, brows, teeth, hair, clothes) and saves `doc_mpfb.blend`, plus turnaround test renders. |
| `doc_pose.py` | Shared helpers: `relaxed_hands`, `pose_arms` (never leave the stiff MPFB A-pose), `rot_world`, `aim`, `key_bones`, and `add_blinks` (random blinks every 2-5 s). |
| `walk.py` | The 3 s walk: IK legs, planted feet, heel strike / toe off, hip bob, opposite arm swing, and a camera that dollies along one axis. |
| `fetch_polyhaven.py` | Downloads CC0 Poly Haven models and textures into `assets/`. |
| `room_set.py` | Living room built from real scans (sofa, chair, shelves, plants, lamp, rug, window light), placed on top of the Doc file. Saves `doc_room.blend`. |
| `room_sit.py` | Footstep planner: walks in from the right, stops at the chair, turns to face the camera, sits, and puts his hands on his thighs. |
| `post.py` | The "real camera" pass: soft lens, glow, vignette and grain. |

## Rebuild the example

```bash
B="C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"
python paint_hoodie.py
"$B" -b --factory-startup -P mpfb_doc.py -- renders 32 front,threequarter 540   # -> renders/doc_mpfb.blend
"$B" -b renders/doc_mpfb.blend -P walk.py -- renders/walk 40 720 all            # 90 frames
python fetch_polyhaven.py sofa_03,Ottoman_01,dining_chair_02,side_table_01,side_table_tall_01,modern_coffee_table_01,wooden_display_shelves_01,modern_ceiling_lamp_01,industrial_wall_sconce,potted_plant_01,potted_plant_02,potted_plant_04,planter_pot_clay,throw_pillows_01,wall_clock,mantel_clock_01,alarm_clock_01,book_encyclopedia_set_01,cassette_player,chess_set,brass_vase_01,ceramic_vase_01,ceramic_vase_02,ceramic_vase_03,ceramic_vase_04,jug_01,wicker_basket_02,wooden_bowl_01,wooden_candlestick,standing_picture_frame_01,standing_picture_frame_02,hanging_picture_frame_01,hanging_picture_frame_02 laminate_floor_02,painted_plaster_wall,fabric_pattern_05
"$B" -b renders/doc_mpfb.blend -P room_set.py -- renders/room_test.png 20 540     # -> renders/doc_room.blend
"$B" -b renders/doc_room.blend -P room_sit.py -- renders/sit 20 720 all
```

Every script takes `<out> <samples> <width> <frames>`. For test frames use `frames` = `1,30,60`. Use `none` to only bake and save the .blend, then render it on Colab, Kaggle or the PC (blender-render-farm).

## How the walk works (keep these numbers)

- **Gait** (`walk.py` top):
  - `T=1.0` s per cycle (two steps). `DUTY=0.6` (share of the cycle a foot is on the ground). `HALF=0.25` m (foot lands this far ahead of the hip).
  - Speed `V = 2*HALF/(DUTY*T)` = 0.83 m/s. This is the ONLY speed at which planted feet don't slide. Change the stride and the speed changes with it.
- **Feet:**
  - Ankle targets are empties (`IK_L/R`).
  - IK on `lowerleg02.L/R`: `chain_count=4`, `use_tail=True`, no stretch.
  - Feet copy the world rotation of `FootRot_L/R` empties.
- **Knees:** pole targets in front of the knees. Calibrate the pole angle by searching for the one where the knee points straight ahead in the rest pose. A wrong pole angle twists the knees inward.
- **Foot roll:**
  - Heel strike: toe 14° up for the first 8 % of the stance.
  - Toe off: the heel peels up to 32° around the ball of the foot.
  - Swing: the foot arcs about 7 cm high with smoothstep easing.
- **Body:**
  - Hips bob 1.4 cm: lowest when both feet are down, highest mid-stance.
  - Arms swing opposite to the legs, on top of the relaxed base pose (`BASE` matrices).
  - Slight spine counter-twist.
- **Camera (Zack rule):**
  - One smooth axis only: a dolly that follows him, with a slight push-in. No orbit and no shake.
  - Ease every move. Measured on Zack: zero sideways pan.
- **Sit (`room_sit.py`):**
  - Plan footsteps toward a stand point in front of the chair, then turn in place over about 0.6 s (the feet step around).
  - Lower the hips with smoothstep onto the raycast seat height.
  - The knees bend through the IK automatically.
  - Hands arc over the thighs (not through them). The targets sit about 8 cm above the thigh surface.

## Mistakes we already fixed (check for them)

- Feet sliding: the speed doesn't match the stride. Use the formula above.
- Stiff MPFB A-pose arms: always call `doc_pose.pose_arms` / `relaxed_hands`.
- The hoodie hood clipped the neck, and a sconce and table blocked the path: in v2 the sconce moved to x=-1.42 and the table moved.
- Hands went through the thighs while sitting: arc the hand targets over the leg.
- No blinks looks dead: `add_blinks` on every shot.
- Before showing anything, render a contact sheet (every 5th frame) and zoom-check feet, hands and face.

## Reference pictures (`reference/`)

Compare your renders to these before showing the user:

- `doc_character_turnaround.jpg`, `doc_face.jpg`: the approved character look (front, three-quarter, side, face).
- `walk_contact_sheet.jpg`: what a correct walk looks like frame by frame (feet planted, heel/toe roll).
- `arms_relaxed_not_Apose.jpg`, `hands_relaxed_test.jpg`: relaxed arms and hands. Never leave the stiff A-pose.
- `sit_contact_sheet_fixed.jpg`, `sit_hands_over_thighs_strip.jpg`: the sit after the fixes (hands arc OVER the thighs).
- `hood_fix_check.jpg`: the hoodie hood no longer clips the neck.
- `room_with_camera_look.jpg`: the living room with `post.py` applied.
- `mpfb_vs_reference.jpg`: our MPFB character next to the realistic reference we were matching.
