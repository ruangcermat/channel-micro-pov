"""Universal 3D Micro-POV Studio Core (`Jadi Apa` / `Jadi Apa 3D`).

Clean separation from episode-specific staging (`04_episodes/epXXX_*/scene_builder.py`):
- `camera_presets.py`: 5 reusable POV camera archetypes + beat modifiers + motion blur
- `mpfb_helpers.py`: Permanent mascot Mas Dimas builder/loader, Leg IK, reach(), ARKit, prop grip
- `lighting_utils.py`: AgX color management, Cycles/EEVEE engine & 2-Gate render presets, HDRI/lights
- `post.py`: Camera look finishing pass (soft lens, highlight glow, vignette, film grain)
- `audio_utils.py`: faster-whisper word timestamps, 15ms VO micro-fade, dynamic -32 dB room_tone
"""
