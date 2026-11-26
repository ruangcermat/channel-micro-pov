# Walkthrough: how the onion short was made (copy this order for every new video)

The video: "Mom was crying", 31.5 s, 945 frames at 30 fps, 9:16.
- Kid laughs at the TV, hears mom crying, confesses his F test, she holds up an onion, a science bit on onion gas, then the twist.
- Final frames: `reference/onion_short_all_15_shots.jpg`.

## Step 1: ask (STEP 0 in SKILL.md)

Ask for the niche (family/science facts), the length (30 s) and whether there's a script (no, so we wrote one).

## Step 2: story and script

- **Pattern** (it works for almost any Zack-style fact):
  1. **Hook:** a relatable moment in 1-2 s.
  2. **Misunderstanding:** raise the stakes.
  3. **Reveal:** the object or fact.
  4. **Science:** 2-3 short sentences, "X releases Y that does Z!"
  5. **Twist:** turns back on the main character.
- **Length:** about 2.7-3 words a second, so 30 s ≈ 85 words. Use "..." for dramatic pauses and CAPS on 1-2 words a sentence for the hype voice.
- **Our script** (`example/voice/vo2.txt`):

  > "I was on the couch, laughing at my favorite show... when I heard Mom CRYING in the kitchen! Oh no. She found my F math test! So I ran in and confessed EVERYTHING! But she just held up... an ONION. Cutting an onion releases a gas that floats straight up into your eyes! It stings... so your eyes FLOOD with tears to wash it away! She wasn't crying because of me... But now... I'M the one about to cry."

- **Fact-check** the science line before voicing. Onions release syn-propanethial-S-oxide gas, which turns into a mild acid on the eye and makes the tear glands flush it.

## Step 3: voice FIRST, then word times

1. `tts_gemini.py vo2.txt vo2_raw.mp3 --whole --voice Fenrir --model gemini-3.8-flash-tts --style "<hype prompt>"`
2. The model reads the style prompt aloud. Transcribe and cut it off: `ffmpeg -ss 7.1 -i vo2_raw.mp3 vo.wav` (find the cut from the first script word's time).
3. Word times: convert to 16 kHz mono wav, then faster-whisper with `word_timestamps=True`, which gives `words.json` and `transcript.json`.
4. **Everything else is timed from words.json.** Never time shots by guessing.

## Step 4: shot list from the word times

One shot per beat, cut ON a word. Our 15:

| t (s) | Shot | Camera | Faces / action |
|---|---|---|---|
| 0.00 | couch | wide 30 mm, the kid on the sofa, slow push | laugh, head bounce |
| 1.65 | tvscreen | over the shoulder onto the TV, 38 mm | laugh |
| 2.80 | laugh | face close-up 55 mm f/2, push-in | laugh |
| 3.85 | hear | close-up, push-in | laugh → shock (hears crying) |
| 5.35 | momback | through the doorway, mom from behind, 30 mm | mom crying, shoulders shake, chopping |
| 6.95 | ohno | kid close-up push-in | panic |
| 8.00 | bagtest | insert: the F test in the backpack, 50 mm | — |
| 10.50 | confess | the kid in the kitchen, 40 mm | guilty, talking (jaw from voice) |
| 13.75 | onion | mom turns, holds up the onion, 40 mm | crying → relieved-ish |
| 17.30 | cut | side close-up: knife and onion on the board, 42 mm | knife in her right hand, onion in her left |
| 20.00 | gas | profile 40 mm, the gas rises from the board to her eyes | sting |
| 21.50 | flood | extreme close-up of the eye, 85 mm | crying, tears grow |
| 25.85 | twoshot | wide side view of both, 24 mm, slow pull | mom relieved, kid guilty |
| 27.95 | angry | mom close-up 60 mm | angry (the F test) |
| 29.50 | kidcry | kid close-up 60 mm | crying, tears |

**Camera rules:**
- Each shot is ONE eased move: `u` from 0 to 1, a push-in of 5-25 %.
- Use f/2-2.8 on faces and f/4-5.6 on wides.
- Focus on the eyes (`focus = head point`).
- No orbit and no sideways pan (measured on Zack).

## Step 5: characters

1. Run `family.py -- renders/family 24 540 pair,mom_crying,kid_shock`, or start from `ready/family_ready.blend`.
2. Check: real bodies under the clothes, MR UDO readable, faces readable at phone size.

## Step 6: sets

1. `fetch_polyhaven.py` for the props.
2. `kitchen_set.py`, then `living_room.py`.
3. Render one test view of each room (`kitchen_set.py -- renders/kitchen_test.png 24 540`).
4. Check:
   - **Window:** the street is visible, not blocked by a tree.
   - **Detail:** 12-20 readable story props (calendar, kid's drawing, fruit, kettle…).
   - **Lighting:** a warm key from the window, with the faces lit brighter than the walls.

## Step 7: bake the animation

```
blender -b renders/kitchen.blend -P kitchen_shots.py -- renders/kshots 16 360 25,67,100,139,185,225,278,364,466,560,623,700,800,880,930
```

1. Render one test frame per shot into a contact sheet.
2. Check each one:
   - **Faces:** expression right? Teeth correct, not grey? Tears visible?
   - **Hands:** knife and onion IN the hands, not floating?
   - **Characters:** each one in the right room? Nobody inside furniture?
   - **Camera:** not inside an object? The black frame came from the camera being inside the toaster.
3. Fix, re-bake, and re-check until every frame passes.
4. Then bake with `none` and use `fix_*.py` for small patches.

## Step 8: render, finish, send

- Use the blender-render-farm skill: Colab, Kaggle or PC. EEVEE works if Cycles is too slow.
- Run `post.py` on every frame, then ffmpeg with `vo.wav`, then `captions.py --words 3 --upper`.
- Do a final contact-sheet check.
- Send it as a VIDEO. Never send a stills slideshow as the result.

## Timings we measured (to plan the work)

| Stage | Time |
|---|---|
| characters | ~1 min a build |
| kitchen set | ~2 min |
| bake | ~6-10 min for 945 frames |
| test frame at 360 px, 16 samples | 15-60 s on CPU |
| final at 720 px, 20 samples | Colab T4 ~11 s/frame (the close-ups 520-776 ~50 s); PC EEVEE ~6 s/frame |
