# Race Photo Strategy — Research & Guidelines

## What Makes Gravel Cycling Photos Go Viral

Research across cycling photography experts, gravel race photographers (Alex Roszko, Ryan Cleek), social media analysis, and cycling influencer data.

### Core Principle: Every Photo Needs a Rider

Empty landscapes are wallpaper. The human element creates emotional connection. Viewers want to see themselves in the photo — imagining what it feels like to ride that road, in that light, through that terrain. A lone cyclist dwarfed by a vast landscape is the single most iconic and shareable image format in gravel cycling.

### The 3 Shot Types That Work

| Shot | Name | What It Conveys | Why It Works |
|------|------|-----------------|--------------|
| **Hero** | Epic Scale | Adventure, freedom, "I want to ride there" | Lone rider + vast landscape = the defining gravel image. Small human figure creates scale and aspiration. Most shareable format. |
| **Grit** | Raw Effort | Suffering, authenticity, "this is real" | Low-angle, dust clouds, gravel spraying from tires. Conveys the texture and physicality that separates gravel from road cycling. Gets engagement through visceral reaction. |
| **Pack** | Community | Belonging, golden hour drama, "the tribe" | Group of riders strung out, backlit by golden light. Captures the social/competitive heart of gravel — you suffer together. Warm atmosphere drives emotional sharing. |

### What Does NOT Work

- **Empty landscapes** — no emotional hook, no human connection, ignored in feeds
- **Terrain close-ups** (rocks, dirt, road surface) — nobody shares a photo of gravel
- **Generic stock** — overly posed, sterile, unbranded kit, studio lighting
- **Close-up faces** — AI uncanny valley risk; always shoot from behind or side

### Composition Rules for AI Prompts

From cycling photography best practices:

1. **GET CLOSE** — then get closer. The best cycling photos have proximity and energy
2. **Low angles** — shooting from ground level looking up at riders makes them look powerful and emphasizes terrain
3. **Leading lines** — roads stretching to horizon guide the eye and create depth
4. **Backlight/golden hour** — warm light + dust = atmosphere. Silhouettes are inherently dramatic
5. **Rule of thirds** — rider placed at intersection points, not dead center
6. **Dust as storytelling** — rooster tails, hanging dust clouds, particles in backlight all convey speed + grit
7. **Scale contrast** — tiny rider vs. massive mountain/desert/prairie = adventure

### Prompt Engineering Notes

- Google recommends **narrative prompts** over keyword lists for Gemini image generation
- Always specify **lens focal length** and **aperture** — this controls framing and depth of field
- Always append **"No text, no watermarks, no logos"** — prevents baked-in text artifacts
- Specify **"no visible face"** — avoids AI uncanny valley issues
- Include **"dust trail behind wheels"** or **"gravel spraying"** for action/energy cues
- Reference **specific terrain and location** from race data for geographic accuracy
- Derive **season and light quality** from race date for temporal accuracy

### Sources

- [ExpertPhotography — Cycling Photography Tips](https://expertphotography.com/cycling-bicycle-images/)
- [FixThePhoto — Cycling Photography Guide](https://fixthephoto.com/cycling-photography.html)
- [Above Category — Interview with Gravel Photographer Alex Roszko](https://abovecategory.com/blogs/journal/shooting-the-breeze-with-gravel-photographer-alex-rozsko)
- [Cycling Weekly — Social Media and Pro Cycling](https://www.cyclingweekly.com/racing/inside-the-world-of-social-media-and-pro-cycling-the-good-the-bad-and-the-viral)
- [CyclingNews — Rise of the Cycling Influencer](https://www.cyclingnews.com/cycling-culture/the-rise-of-the-cycling-influencer-how-gen-z-and-millennial-riders-are-bringing-cycling-to-the-social-media-generation/)
- [Ryan Cleek — Gravel Cycling Photography](https://ryancleekproductions.com/commercial-photography/adventure-sports-photography/gravel-cycling/)
- [Shimano — Cycling Photography 101](https://bike.shimano.com/en-EU/stories/article/cycling-photography-101.html)

## Technical Specs

| Field | Value |
|-------|-------|
| Model | `gemini-2.5-flash-image` |
| Photo types | `hero` (16:9), `grit` (4:3), `pack` (16:9) |
| Output | 1200px wide JPEG, quality 85 |
| Dimensions | hero 1200x675, grit 1200x900, pack 1200x675 |
| Output dir | `wordpress/output/photos/` |
| Deploy path | `https://gravelgodcycling.com/photos/{slug}-{type}.jpg` |
| Cost | ~$0.039/image, ~$38 total for 984 images |
| Concurrency | 3 default (500 RPM paid tier) |
| Race data fields used | `vitals.location`, `vitals.terrain_types`, `vitals.date_specific`, `terrain.primary`, `terrain.surface`, `terrain.features`, `climate.primary`, `climate.description`, `course_description.character`, `gravel_god_rating.discipline` |
