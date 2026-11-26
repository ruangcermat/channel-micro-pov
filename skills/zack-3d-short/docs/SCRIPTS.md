# What every script does

Arguments, inputs, outputs, and the functions worth reusing.

Every Blender script runs headless:

```
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b <input.blend or --factory-startup> -P <script.py> -- <args>
```

Scripts find their files relative to their own folder (`HERE`). Keep `assets/`, `tex/`, `renders/` and `kitchen/` next to them.

## Build order and data flow

```
                  paint_family.py ──► tex/kid_tee_diffuse.png, tex/mom_tee_diffuse.png
                         │
family.py (MPFB) ────────┴──► renders/family.blend          ◄── OR start from ready/family_ready.blend
make_kitchen_tex.py ─────────► tex/calendar.png, tex/drawing.png
fetch_polyhaven.py ──────────► assets/<model>/<model>.gltf, assets/tex_<name>/...
kitchen_set.py  (opens family.blend, imports street.py) ──► renders/kitchen.blend
living_room.py  (opens kitchen.blend, appends doc_room.blend) ──► renders/kitchen.blend (overwritten)
kitchen_shots.py (opens kitchen.blend, reads kitchen/vo.wav) ──► renders/kitchen_anim.blend  (+ test PNGs)
fix_gas.py / fix_teeth.py / fix_tv.py (open kitchen_anim.blend, patch, save)
render_frames.py / blender-render-farm ──► frames ──► post.py ──► ffmpeg + voice + captions
```

## paint_family.py (system Python: pillow, numpy)

- **Reads:** MPFB's own clothes textures from `%APPDATA%/.../mpfb/data/clothes/<suit>/`. Change `SRC` on Mac or Linux.
- **Writes:** `tex/kid_tee_diffuse.png` (red tee with white "MR UDO") and `tex/mom_tee_diffuse.png` (sage green).
- `uv_mask(obj_name)`: rasterises the garment's UV islands from its `.obj`, so you only recolour fabric.
- `recolour(img, box, rgb, keep=.85)`: shifts the hue and saturation but keeps the fabric shading and wrinkles.
- `patch(img, box, src_box)`: copies plain fabric over the stock logo.
- **Text:** `FONT` (Arial Black), drawn at `tx, ty` with width `tw` in UV pixels. To move it, change those 3 numbers, re-run, then re-run family.py and check a front render.
- **To make a new shirt:** copy the kid block, change the colour or the text, and save a new file name. Pass that file name as the `tex` argument of `make()`.

## family.py

- **Args:** `<out_dir> <samples> <width> <views>`
- **Views:**
  - `pair`: both, full body
  - `momfull` / `kidfull`
  - `mom_<expr>` / `kid_<expr>`: a face close-up with that expression
- **Env:** `EXPR_BOOST` (default 1.6).
- `make(name, phenotype, targets, hair, brows, suit, shoes, skin, tex)` builds one human, returning `(rig, body, new_objects)`. It:
  - adds a Displace of 0.006 on the clothes (stops skin poking through)
  - retextures the shirt with `tex`
  - pre-loads the face units
- `set_expr(body, name)` sets `!ex-` keys only.
- `add_tears(rig, body, name)` builds the raycast tear curves and the lid curves, parented to the head.
- **Studio:** a blue backdrop (RGB 82,164,222, the Zack blue), key, fill and two rims, and a camera rig.
- **Saves** `renders/family.blend`.

## ready/family_ready.blend (no MPFB needed to USE it)

- The mom and kid, fully built, with every texture packed (1K, plenty for phone video).
- `kitchen_set.py` can open it directly instead of `family.blend`:

  ```
  blender -b ready/family_ready.blend -P kitchen_set.py -- none 24 540
  ```

- **Rebuilding or changing a character still needs MPFB plus family.py.** Moving, posing and changing faces does not.

## kitchen_set.py

- **Args:** `<out_png|none> <samples> <width>`.
- **Opens** the family file and deletes the studio objects. **Saves** `renders/kitchen.blend`.
- **Helpers you'll reuse for ANY set:**
  - `tex_mat(name, polyhaven_tex, scale, rough, tint, bump)`: a Poly Haven PBR material with box-mapped UVs.
  - `plain(name, rgb, rough, metal, emit, coat)`: a flat material.
  - `box(name, centre, size, mat, bevel)`, `quad(name, 4pts, mat)`, `cyl(name, centre, r, h, mat)`: bevelled primitives.
  - `place(asset, loc, rot_z, scale, name)`: imports `assets/<asset>/<asset>.gltf` under an empty you can move.
  - `picture(name, path, centre, w, h, normal_axis)`: a framed image on a wall (calendar, drawing).
  - `area(name, loc, target, size, energy, col)`: an area light aimed at a point.
- **Layout constants:**
  - `CT` = worktop height 0.92
  - `WIN` = window x0, x1, z0, z1 in the back wall
  - `DOOR`, `BOARD`, `TABLE`
  - Room X -2.3..2.3, Y -2.6..1.8 (`Y1` = back wall), ceiling 2.6
- `chef_knife()`: a code-built knife (blade with an edge bevel, a handle and 3 rivets) under the `Knife` empty.
- **Props are named** so the shot script can find them: `Board`, `OnionWhole`, `OnionSpare`, `Knife`.

## street.py

- `build(sc, origin, plain, box, quad, cyl, seed, x_span)` builds everything outside the window: grass, pavement, a road with dashes, a picket fence, houses (random widths, roof colours, windows, doors), trees, a parked car and a lamp post.
- Change `seed` for a different street.
- Keep the trees out of the window's line of sight (we moved one that blocked it).

## living_room.py

- **Appends** `renders/doc_room.blend` (built by blender-walk-example `room_set.py`) at x+12, without its character.
- **Adds:**
  - the front wall
  - the TV on a cabinet, plus `TVGlow` light
  - `SofaBackpack`, `BagTest` (F paper) and `Remote`
- Raycasts the sofa seat and stores `sc["sofa_seat_z"]`, `sc["sofa_pos"]` and `sc["tv_pos"]` for the shot script.
- **No doc_room.blend?** Build it with blender-walk-example (`mpfb_doc.py`, then `room_set.py`). Or skip this script and keep the story in one room.

## kitchen_shots.py (the director)

- **Args:** `<out_dir> <samples> <width> <frames|all|none>`.
  - `none` = bake and save only.
  - `1,50,120` = bake, then render those test frames.
- **Reads** `kitchen/vo.wav` for mouth loudness. `DUR`, `FPS` = 30 and `N` frames come from the voice length.
- **Sections in order:**
  1. **voice loudness:** `LOUD[f]`
  2. **faces:**
     - `EXPR`
     - `set_face(body, t, e1, e2, k, talk, f)`: blend expression e1 to e2 by k, then key it
     - `set_tears(who, amount, f)`
     - blinks
  3. **legs:** IK set up per rig. `set_poles(arm, loc, yaw, f)`, `feet_standing(arm, loc, yaw, f)`, `sit_kid(f, swing)`.
  4. **arms:**
     - `reach(arm, side, world_target, pole)`
     - `lean(arm, deg)`
     - `head_turn(arm, yaw, pitch)`
     - `key_pose(arm, f)`
  5. **props:**
     - The knife and onion snap to the hands every frame.
     - The gas volume material plus 16 `GasPuff` spheres.
  6. **layout:** `MOM_POS`, `KID_STOP`, `SHOTS`, `shot_at(t)` → (shot name, u = 0..1 through the shot, seconds into the shot).
  7. **camera:** `set_cam(loc, target, lens, focus_point, f, fstop)`, which keys location, rotation, lens and DOF.
  8. **per-frame bake:** for every frame:
     - reset the pose
     - place the characters
     - set faces, tears, arms, props, gas
     - pick the camera for the shot
     - key everything
- **Saves** `renders/kitchen_anim.blend`.

## fix_gas.py / fix_teeth.py / fix_tv.py

- **These are small patches on the baked file.** Re-baking takes about 10 minutes; a patch takes seconds.
- **fix_gas:** keys `hide_render` on the puffs instead of scale 0 (scale 0 crashed Cycles at frame 711).
- **fix_teeth:** relinks the teeth texture to Base Color (gums were grey).
- **fix_tv:** swaps the TV image sequence for 3 still images switched by keyed Mix nodes, because sequences can't be packed for cloud rendering.

## render_frames.py

```
-- <out_dir> <samples> <width> <frames>
```

- `frames` = `1,5,9`, `100-200`, or `@list.txt`.
- It skips frames that already exist and prints `FRAME n secs`. The output is `k_0001.png` and so on, at 9:16.

## post.py (system Python)

```
python post.py in.png out.png
```

It applies, in order:
1. soft lens (35 % of a 0.7 px blur)
2. glow on highlights (screen blend)
3. vignette (28 %)
4. film grain (stronger in the shadows)

It scales with the image width. Run it on every frame before ffmpeg.

## fetch_polyhaven.py

```
python fetch_polyhaven.py <model,model,...> [texture,texture,...]
```

- Downloads 1K glTF models and 1K PBR textures from the Poly Haven API into `assets/`. It skips files already there.
- Find asset names at https://polyhaven.com/models and https://polyhaven.com/textures. The name is the last part of the URL.
- `polyhaven_assets.txt` lists every asset our sets use.
