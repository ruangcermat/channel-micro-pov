# Troubleshooting: every real bug we hit, and the fix

Before showing the user ANY frame, check this list.

## Characters

| What you see | Cause | Fix |
|---|---|---|
| Only clothes, no body ("no bodies just clothes") | the code zeroed every shape key, including the `$md-` BODY keys | Reset only keys starting with `!ex-` |
| Eyes, teeth, hair or clothes float away when the body moves | not parented to the rig | Parent to `<Name>_rig` and keep the armature modifier |
| Skin pokes through socks or the shirt | the cloth sits too close to the body | Displace modifier 0.006 on the clothes |
| Waxy, game-like skin | the default skin material | `skin_material_type = "ENHANCED_SSS"`, matte roughness |
| Stiff A-pose arms | MPFB rest pose | `doc_pose.pose_arms` / `relaxed_hands` every shot |
| Green or odd-coloured teeth | grass or wall bounce light | Fix the LIGHT. Never tint the teeth. |
| Grey teeth and gums | flat colour replaced the texture | Teeth texture → Base Color (`fix_teeth.py`) |
| Mouth opens but the teeth stay shut | only the `jawOpen` key was used | Rotate the `jaw` BONE (17° × jaw). The key only goes to 0.25 of that. |
| Expression too subtle on a phone | values too small | BOOST 1.6; the eyebrows do most of the acting |
| A new face unit does nothing | the unit wasn't loaded at build time | Add it to the `set_expression` warm-up dict and rebuild |
| Tears invisible | too thin, or no highlight | bevel 0.0021, transmission material, a rim light; check at an 85 mm close-up |
| T-shirt text mirrored or cut | the UV island is flipped or crosses a seam | Move `tx/ty/tw` in paint_family.py; check a FRONT render at full size |
| Hands sink into the thighs when sitting | hand target on the thigh surface | Targets at thigh top +0.085 m; arc the hands over the leg |

## Props and staging

| What you see | Cause | Fix |
|---|---|---|
| Knife or onion floating ("props are flying") | the prop is placed in the world, not from the hand | Each frame: `prop = wrist.head + palm_dir*0.055 + up*0.045`, with rotation from the wrist |
| No knife visible | hidden behind the body or the wrong side | Put the knife in the hand nearest the camera; a side angle for the cut shot |
| A character in the wrong room (the kid in the kitchen while "on the sofa") | the placement doesn't follow the story | Per-shot placement: kid on the sofa for the living-room shots AND momback |
| The two-shot shows an empty kitchen | the characters are 1.8 m apart and the camera too close | Pull back from the side, 24 mm, frame both |
| Black frame | camera inside an object (the toaster) | Raycast from the camera to the target; move the camera |
| A tree blocks the window view | a random tree placement | Keep the trees off the window line |

## Gas, smoke and volumes

| What you see | Cause | Fix |
|---|---|---|
| Gas invisible | density too low | Density about 170 (it went 9, then 260, then 170) |
| Gas looks like flying solid blobs | hard spheres | 4D noise times a radial falloff, emission 2.5, puffs grow and drift upward |
| Cycles silently exits mid-render (frame 711) | a puff scaled to about 0 | Key `hide_render` instead of scale 0 (`fix_gas.py`) |

## Rendering

| What you see | Cause | Fix |
|---|---|---|
| Pink objects | missing textures (not packed, or an image sequence) | `pack.py` must print `MISSING []`; replace sequences with keyed Mix nodes (`fix_tv.py`) |
| Colab lost every frame | tab closed, interrupted, or the GPU limit was hit | Keep the tab open, never Interrupt, zip-download every ~200 frames |
| Kaggle stuck on "Queued…" | GPU queue | Wait, or Stop it from the "Event running" chip (needs a foreground tab) |
| `.blend` corrupt after joining the parts | joined in text order (part10 before part2) | Numeric sort: `int(p.rsplit('part',1)[1])` |
| Close-ups about 5× slower than other shots | unknown (not gas, DOF, street or tears) | Per-shot `hide_render` of off-camera objects; or EEVEE |
| EEVEE first frame takes about 50 s | shader compile | Normal; the next frames take about 6 s |

## Delivery

| What you see | Cause | Fix |
|---|---|---|
| User: "it's just images not a vid" | sent a stills slideshow | Only ever send a real rendered video as the result |
| The voice reads the style instructions | Gemini reads the `--style` prefix aloud | Transcribe, then `ffmpeg -ss <first script word>` |
| `av.open` fails on mp3 | whisper input format | Convert to 16 kHz mono wav first |
