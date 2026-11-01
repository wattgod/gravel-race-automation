# Papercuts

Small frictions hit while working. Not bugs, not accomplishments — where this repo needs sanding down.

- 2026-10-28 [claude-opus-5-5] running the full pytest suite on fresh main -> tests/test_article_conversion.py and tests/test_substack_import.py import bs4, which isn't in the local Python, so collection stops; add beautifulsoup4 to requirements or importorskip
- 2026-11-01 [claude-opus-5-5] Reframing guide art -> the <img height=640> attribute silently overrode the CSS aspect-ratio crop, so phones showed a thin sliver of the handbook art; fixed with height:auto, worth a test.
- 2026-11-01 [claude-opus-5-5] Replacing /guide/media art -> files are served with a 1-year cache and no content hash, so same-name swaps would stay stale; had to rename to gg-art-v67-*.
- 2026-11-01 [claude-opus-5.5] Re-rendering Substack articles (scripts/import_substack_posts.py) -> system python3 had no bs4 although requirements.txt lists it; had to pip install --user. No repo venv documented for article work.
- 2026-11-01 [claude-opus-5-5] redrawing v6.7 character stickers -> erase 'clone' copies nearby speech bubbles, notepad text and surgeons into the hole; it needs a way to exclude regions (bubbles/text) from the source patches
- 2026-11-01 [claude-opus-5-5] redrawing v67 art, re-reading a compare PNG at the same path -> the image viewer showed the stale first version; write each review sheet to a new filename
- 2026-11-01 [claude-opus-5-5] measuring old-cartoon boxes from the 10% grid sheets -> boxes came out 50-100px off and left hat brims behind; a zoomed crop with a 50px labelled grid (scratchpad g4/zoom.py) fixed it
- 2026-11-01 [claude-opus-5-5] v67 art specs: erase 'clone' copies the neighbouring patch even when that patch is a speech bubble or another object (SUV, bubble text duplicated next to the figure); 'telea'+mask 'grabcut' is the reliable default on photos — maybe make clone skip patches overlapping texts/bubbles or default to grabcut+telea
- 2026-11-01 [claude-opus-5-5] character redraw: removing a big fedora from a photo with inpainting (telea/shiftmap/clone) leaves smears or rectangles; stretching a texture strip from beside the hole (rebuild + insets) worked best — renderer could use a 'stretch fill' erase mode
- 2026-11-01 [claude-opus-5-5] redrawing photo stickers with render_character_art_v67 -> clone/telea/shiftmap erase all smear or leave seams on busy photos; had to fake background with inset strips copied from elsewhere. An 'inset tile/repeat' option or a better inpainter would save many retries.
- 2026-11-01 [claude-opus-5-5] group 3 v6.7 redraw -> clone erase copies nearby objects (a donkey, a woman) into the hole, and telea smears painted scenes; on busy AI paintings only rebuild/scene mode came out clean, which costs many render passes per image
- 2026-11-01 [claude-opus-5-5] redrawing big painted characters -> none of clone/telea/shiftmap fills a large hole cleanly: shiftmap and clone copy nearby speech bubbles/objects into it, telea smears; for painted AI scenes the scene mode or a rebuild is the only clean route
- 2026-11-01 [claude-opus-5-5] redrawing v67 group 6 -> telea/clone fills smear badly where an old hat sat over real photos; only a hand-placed flat fill or rebuild looks clean, and there is no 'gradient fill' erase option
- 2026-11-01 [claude-opus-5-5] redrawing sweet-spot memes -> each meme's phone file (-m) is a separately restacked layout, not a crop, so every meme needed a second hand-built spec row; also shiftmap erase on flat panels copied caption text into the hole
