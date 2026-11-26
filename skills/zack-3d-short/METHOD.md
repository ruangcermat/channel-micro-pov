# Zack-style 3D short: method learned from Mr Omi's video (youtu.be/_fIoJ_ywGfY)

Studied 2026-11-17: full transcript plus a frame every 4 s (edits/study_char_method/).
He sells the finished skill. Everything below is what he SHOWED and SAID in the free video.

## 1. Measure the reference first
- Download the top Zack shorts and analyse every frame at 30 fps.
- Measure camera motion with phase correlation: shift and zoom between each pair of frames.
- Measured numbers on the reference:
  - **Camera:** zero sideways pan. A straight dolly in, hold, then an eased pull-out. One continuous shot (the stitches short has no cuts).
  - **Small motion:** keeps moving during the hold. A new stitch lands every 6-8 frames.
  - **Hard cuts:** only about 1 in 7 transitions. The rest are whip pans or zoom-throughs, where the camera flies into the next scene.
  - **Blue background:** RGB 82,164,222.
  - **Speech:** median 2.77 words/s, calm.
  - **Hooks:** 16 of the 50 open with "If you…".
  - **Mix:** about -15 LUFS, almost no dynamic range.
- **THE TIP:** run OUR render through the same measuring pipeline. The difference between the two sets of numbers is the to-do list.
  - His first test camera had 8x the jerk (rate of change of acceleration) of Zack's.
  - Fix: lock the camera to one dolly axis, ease every move, no orbit drift.

## 2. Character
- Scanned humans look real but can't act: one solid surface (no body under the clothes) and a face rig with only a jaw.
- MetaHuman was a dead end: needs an account and token.
- **Used:** MPFB2 (MakeHuman for Blender), from Blender's official extension site.
  - Free, no account, checksum-verified.
  - Has 52 face shape keys (the same set as iPhone ARKit face capture): browUp, eyeWide, jawOpen and so on, which give real expressions.
- **Problems he hit, and the fixes:**
  - Waxy game-character look. Fix: matte skin, real pores, subsurface scattering (light through the skin).
  - Stock t-shirt logo. Fix: swap it.
  - Eyes, teeth, hair and shirt floating off the body. Fix: they must be parented to the armature.
  - Green teeth were grass bounce light, not the texture. Don't tint-fix lighting problems.

## 3. Sets
- **Rule:** if a real asset exists, download it (Poly Haven, scans, NASA imagery, anatomy databases). Never hand-build it. Hand-built stadium = "AI slop".
- **Copy the reference's simplicity:** the top-down shot is just the field floating on light blue.
- Photo backdrop + an invisible "shadow catcher" floor beats fake 3D grass.
- Volumetric clouds, not solid blobs.

## 4. Look (from 21 photoreal tutorials)
- Renders are "too perfect". Add camera flaws:
  - Softer lens
  - Glow/bloom on bright spots
  - Vignette
  - Film grain
  - Motion blur on fast moves
- **Colour mode:** Blender's default view transform muted the blue. Pick one that keeps the approved blue AND stops highlights clipping to flat white (not plain Standard).
- **Light:** low sun, long shadows, natural falloff.
- A separate judge agent scores stills (7 → 7.5 → 8.5/10) before the final render.

## 5. Sound
- Room-tone base under everything, so there's never dead silence.
- Stacked hits on big moments: low weight layer + main sound + high detail.
- Reverb follows the camera.
- 19 tracks for 9 seconds.
- Effects land on the exact frame of the word ("bone knock" on "bones").
- His mix rule: music +3 dB, effects at half, voice unchanged. Target about -15 LUFS.

## 6. Render speed (Cycles)
- Render at 1080, upscale to 2K: no visible difference on a phone.
- Put a timer per frame to find slow parts:
  - Haze emission counted as lights (big light list every frame). Turn off.
  - Clouds in the slow volume mode. Switch mode.
- Run 2 Blender processes at once.
- Result: 11 h → 61 min (he has a GPU; we only have CPU, an i7-9700, so expect slower).
