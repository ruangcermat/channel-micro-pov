---
name: blender-render-farm
description: Render a finished (baked) Blender .blend into a real moving MP4 - on free Google Colab GPU, Kaggle GPU, or this PC (Cycles with 2 processes, or the fast EEVEE switch) - then add the camera look, voice and captions. Includes packing, splitting into 9 MB parts for browser upload, the notebooks, the resume logic, and every failure we hit. Use when the user says render it, render on Colab / Kaggle / the PC, "make it a real video", "it's just images", or when a Cycles render is too slow.
---

# Blender render farm (Colab, Kaggle, PC)

Input: a baked `.blend` (the animation keyed on every frame, e.g. `renders/kitchen_anim.blend`).
Output: `final.mp4` with the camera look, voice and captions.

**Golden rule:** the user wants a MOVING VIDEO. Never send a slideshow of stills as the result. Only send stills when they're labelled as test frames.

## 1. Choose where to render (decide from real timings)

First, time 2 frames on the PC: one normal frame and the slowest close-up.

```bash
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b scene.blend -P scripts/render_frames.py -- renders/t 20 720 100,600
```

| Option | Speed (our onion short, 945 frames, 720 px) | When |
|---|---|---|
| **PC EEVEE** (`eevee_switch.py`) | about 6 s/frame after a one-time ~50 s shader compile, so roughly 1.5 h | The default when Cycles is too slow. Softer realism. Test 1 frame first. |
| **PC Cycles, 2 processes** (`render_pc.ps1`) | about 25-50 s/frame on the i7-9700 CPU | Short clips (under 150 frames). |
| **Colab free T4** | about 11 s/frame (close-ups up to about 50 s) | Medium renders. There's a daily GPU limit. |
| **Kaggle 2×T4** | similar to Colab, 30 GPU h/week, runs with the tab closed | Long renders, if it isn't stuck in "Queued". |
| **Colab paid A100** | about 4× a T4 | The USER buys the units themself. Never enter payment details. |

**Never** use extra Google accounts to get around Colab limits.

## 2. Pack, then split (cloud only)

```bash
B="C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"
"$B" -b renders/scene_anim.blend -P scripts/pack.py -- upload/scene_packed.blend   # prints MISSING [] -> must be empty
python scripts/split_blend.py upload/scene_packed.blend upload/parts 9             # 9 MB parts
cp scripts/post.py upload/parts/
```

- **Image sequences can't be packed.**
  - Replace one with N single images switched by keyed Mix nodes. See `zack-3d-short/scripts/fix_tv.py`.
  - Otherwise the cloud render shows pink.
- **The Chrome extension's `file_upload` caps at about 10.4 MB per call.** That's why the parts are 9 MB.
- **The joins in both notebooks sort numerically:** `key=lambda p: int(p.rsplit('part',1)[1])`. Plain sort puts part10 before part2 and corrupts the .blend.

## 3. Google Colab (`notebooks/colab_render.ipynb`)

1. In Chrome, go to colab.research.google.com, then File → Upload notebook → `colab_render.ipynb`.
2. Runtime → Change runtime type → **T4 GPU**.
3. Upload all `*.blend.part*` files plus `post.py` to the Files panel (left), with the extension's `file_upload` into the Files panel drop zone. Wait until every upload finishes.
4. Edit the SETTINGS cell (`SAMPLES`, `WIDTH`, `START`, `END`).
   - If an edit lands in the wrong place, click into the cell, press ctrl+a, and retype the whole cell.
5. Runtime → **Run all**.
   - The render cell prints `FRAME n/END  x.xs`.
   - At the end, the notebook runs post.py on every frame, then ffmpeg, then downloads `doc_render.mp4`.

**Colab traps (all of these happened):**

- **Closing or reloading the Colab tab kills the runtime, and every frame is lost.**
  - Keep the tab open.
  - Ask for keep-awake (`mcp__ccd_host__request_keep_awake`).
- **The free GPU has a daily usage limit.** When it's hit, the runtime disconnects and the frames are gone.
  - On long jobs, zip and download `frames/` every ~200 frames with a cell: `!cd /content && zip -qr part.zip frames` then `files.download`.
  - Or split the frame range over several runs.
- **The render script skips frames that already exist,** so re-running the cell resumes, but only inside the same runtime.
- Don't press Interrupt to "check" on it. The interrupt plus the limit lost 532 frames.

## 4. Kaggle (`notebooks/kaggle_render.ipynb`)

- **One-time setup:**
  - The user makes the account and verifies their phone themself (no phone means no GPU).
  - Create → New Dataset → upload the parts plus post.py, private.
  - Create → New Notebook → File → Import → `kaggle_render.ipynb`.
  - Session options: GPU T4 x2, Internet On, Add Input → the dataset.
- **Long runs:** Save Version → **Save & Run All (Commit)**. It runs with the browser closed. Get the results from the Output tab (`doc_render.mp4`, `frames.zip`).
- **Trap:** a commit can sit in "Queued…" for 30+ minutes. To cancel, go to the "Event running" chip → Stop. That needs a foreground tab.
- **Split work:** Colab does `1-472` and Kaggle does `473-945` (set `START`/`END`), then join the frames on the PC.
- The notebook forces the OpenImageDenoise denoiser (the T4 driver fails with OptiX) and falls back OptiX → CUDA → CPU.

## 5. PC rendering

```powershell
# EEVEE (fast): switch, test one frame, then all
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b renders\scene_anim.blend -P scripts\eevee_switch.py -- renders\scene_eevee.blend 32
powershell -File scripts\render_pc.ps1 -Blend renders\scene_eevee.blend -Out renders\frames -Samples 32 -Width 720 -Start 1 -End 945 -Procs 1
# Cycles: 2 processes in parallel (each takes every 2nd frame)
powershell -File scripts\render_pc.ps1 -Blend renders\scene_anim.blend -Out renders\frames -Samples 20 -Width 720 -Start 1 -End 945 -Procs 2
```

- **Keep the PC from sleeping:** call `mcp__ccd_host__request_keep_awake`.
- **Run long renders in the background** (`run_in_background`). Watch the `log_*.txt` FRAME lines, and send the user progress frames as they finish.
- **Resume:** run the same command again. `render_frames.py` skips any `k_XXXX.png` that already exists.
- **EEVEE notes:**
  - One process at a time: EEVEE uses the GPU or iGPU, and two processes fight over it.
  - Volumes (gas puffs) and SSS skin look softer.
  - If a shot looks dark, raise the light energy a little rather than the exposure.
- **Slow Cycles shots:**
  - Put a timer on each frame (render_frames prints seconds per frame).
  - Bisect by hiding object groups in a copy of the file.
  - Known causes:
    - Emissive haze counted as lights.
    - Volumes in the slow mode.
    - Puffs scaled to ~0 (that one crashes Cycles: hide them instead).
    - Huge out-of-shot sets. Hide what the camera can't see per shot with keyed `hide_render`.

## 6. Finish the video (always)

```bash
python scripts/post.py in.png out.png        # per frame: soft lens, glow, vignette, grain (or use the notebook's post step)
ffmpeg -y -framerate 30 -i post/k_%04d.png -i vo.wav -c:v libx264 -pix_fmt yuv420p -crf 17 -c:a aac -b:a 192k -shortest out_novo_cap.mp4
python C:/Users/Admin/.claude/skills/video-editor/scripts/captions.py out_novo_cap.mp4 transcript.json final.mp4 --words 3 --upper
```

- The frame names from `render_frames.py` are `k_%04d.png`, and from the notebooks `frame_%04d.png`. Add `-start_number N` if the range doesn't start at 0 or 1.
- Before sending:
  - Pull a contact sheet (every 15th frame) and zoom-check it: faces, hands, props, flicker.
  - Check the audio sync on 3 words.
- Send the MP4 with SendUserFile. For WhatsApp or upload, keep it under 16 MB (`-crf 23`).

## Reference pictures (`reference/`)

- `colab_T4_vs_pc_same_frame.jpg`: the same frame rendered on Colab and on the PC. They must match; if Colab looks different, textures are missing or the settings differ.
- `eevee_test_frame.jpg`: what the EEVEE switch looks like (about 6 s/frame) next to the Cycles look.
