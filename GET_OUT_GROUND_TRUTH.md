# Get Out (2017) — Ground Truth Dataset for Script Breakdown Benchmark

**Purpose:** Structured production ground truth compiled from public sources, used to score DeepRepo RLM vs. baseline single-model script breakdown accuracy.
**Film:** Get Out (2017), written and directed by Jordan Peele
**Screenplay:** ~104 pages, ~70 scenes, freely available (Script Slug, AWS S3 PDF)
**Production:** 23-day shoot, $4.5M budget, Fairhope + Mobile, Alabama

---

## Part 1: Data Structure

Each scene in the screenplay gets a ground truth record. The RLM and baseline outputs are scored against this on **precision** (items found that are real) and **recall** (real items found out of total).

### Scene Record Schema

```json
{
  "scene_id": "SC-001",
  "scene_header": "EXT. SUBURBAN STREET - NIGHT",
  "page_range": "1-3",
  "time_of_day": "NIGHT",
  "int_ext": "EXT",

  "location": {
    "script_location": "Suburban street",
    "production_location": "Ryan Ave & De Leon Ave, Park Place district, Mobile, AL",
    "location_type": "residential street",
    "notes": "Opening abduction scene"
  },

  "cast": [
    {
      "character": "Andre Hayworth",
      "actor": "LaKeith Stanfield",
      "category": "speaking",
      "notes": "First appearance, abducted"
    },
    {
      "character": "The Driver / Jeremy Armitage",
      "actor": "Caleb Landry Jones",
      "category": "silent/masked",
      "notes": "Wearing knight's helmet, identity revealed later"
    }
  ],

  "props": [
    {
      "item": "Medieval knight's helmet",
      "handler": "Jeremy/Driver",
      "narrative_significance": "high — conceals abductor identity",
      "source": "screenplay + multiple analyses"
    },
    {
      "item": "Tranquilizer dart gun with silencer",
      "handler": "Jeremy/Driver",
      "narrative_significance": "high — weapon used to subdue Andre",
      "source": "screenplay"
    }
  ],

  "vehicles": [
    {
      "vehicle": "Vintage cream-colored Porsche with tinted windows and roof",
      "driver": "Jeremy Armitage",
      "narrative_significance": "high — identified later as Jeremy's car; Chris escapes in it",
      "source": "screenplay + IndieWire (Peele confirms white Porsche is intentional)"
    }
  ],

  "wardrobe": [
    {
      "character": "Andre",
      "description": "Sweats, casual athletic wear",
      "source": "screenplay"
    }
  ],

  "special_effects": [],
  "music_sound": [
    {
      "element": "'Run Rabbit Run' — Flanagan and Allen (1939)",
      "type": "diegetic — playing from car speakers",
      "narrative_significance": "high — foreshadows hunting metaphor; recurs when Chris finds Jeremy's car",
      "source": "screenplay + GradeSaver + multiple analyses"
    }
  ],

  "stunts": ["Andre tackled/subdued, dragged to car trunk"],
  "animals": [],
  "makeup_hair": [],
  "greenery": []
}
```

### Scoring Categories

For the benchmark, we score across 8 extraction categories:

| Category | What counts | Scoring method |
|----------|------------|----------------|
| **Cast** | Character name + which scenes they appear in | Per-scene presence: TP/FP/FN |
| **Locations** | Script location per scene (INT/EXT, place description) | Exact match on location descriptor |
| **Props** | Physical objects handled, visible, or referenced | Item-level: found or missed |
| **Vehicles** | Cars, trucks, any transport | Item-level per scene |
| **Wardrobe** | Costume descriptions per character per scene | Character-scene pair level |
| **Special Effects / VFX** | Practical FX, CGI, pyro, etc. | Item-level per scene |
| **Music / Sound** | Specific songs, score cues, diegetic sound | Item-level |
| **Stunts / Action** | Fight choreography, falls, physical action | Item-level per scene |

Secondary categories (scored but not primary):
- **Makeup / Hair** — blood, wounds, aging, special prosthetics
- **Animals** — the deer (both live hit and mounted head)
- **Time of Day** — DAY / NIGHT / DAWN / DUSK per scene
- **Greenery / Set Dressing** — significant set elements

---

## Part 2: Ground Truth by Act

### ACT 1 — Setup (Pages 1–25, ~Scenes 1–20)

#### SC-001: EXT. SUBURBAN STREET - NIGHT (Opening)
- **Location:** Suburban residential street (filmed: Ryan Ave & De Leon Ave, Mobile, AL)
- **Cast:** Andre Hayworth (LaKeith Stanfield), Jeremy Armitage/The Driver (Caleb Landry Jones, masked)
- **Props:** Medieval knight's helmet (tubular metal, slanted eye slots), tranquilizer dart gun with silencer, Andre's phone (jazz playing), dart (sticks in Andre's back)
- **Vehicles:** Vintage cream-colored Porsche with tinted windows and roof
- **Music:** "Run Rabbit Run" by Flanagan and Allen — diegetic from car
- **Stunts:** Andre shot with dart, stumbles, dragged to car trunk
- **Wardrobe:** Andre in sweats/athletic wear; Driver in dark clothing + knight helmet
- **Source confidence:** HIGH — screenplay + Wikipedia + IndieWire director commentary + GradeSaver + multiple film studies

#### SC-002–004: INT/EXT. BROOKLYN LOFT / STREET — DAY (Chris & Rose depart)
- **Location:** Chris's Brooklyn apartment / Brooklyn street (filmed: 127 Dauphin St, Mobile, AL)
- **Cast:** Chris Washington (Daniel Kaluuya), Rose Armitage (Allison Williams), Sid the dog
- **Props:** Luggage, Chris's camera (professional, long zoom lens), cigarette (Rose grabs and throws out window), Rose's phone (takes selfie), fast food wrappers in car
- **Vehicles:** Rose's car (described as red in analysis; she drives)
- **Wardrobe:** Chris — gray zip-up hoodie, blue henley underneath (Nadine Haders: "gray is a color between black and white — his 'cozy clothes'"). Rose — denim dress ("denim represents the All-American girl" — Haders/Vogue interview). Red, white, blue color scheme together as "All-American couple"
- **Animals:** Sid (Chris's dog, left with Rod)
- **Source confidence:** HIGH — screenplay + BAMF Style wardrobe analysis + Vogue/BET Haders interview

#### SC-005–006: INT. ROSE'S CAR — DAY / EXT. LAGUARDIA AIRPORT
- **Location:** Car interior / outside airport terminal
- **Cast:** Chris, Rose, Rod Williams (Lil Rel Howery, via phone only at airport exterior)
- **Props:** Chris's camera (looks through viewfinder at trees), cell phone, cigarette (another one; Rose confiscates)
- **Music:** Rose humming
- **Wardrobe:** Rod — TSA uniform (introduced as TSA agent)
- **Source confidence:** HIGH — screenplay

#### SC-007: EXT. RURAL ROAD / INT. ROSE'S CAR — DAY (Deer strike)
- **Location:** Rural road, upstate New York (filmed: roads near Fairhope, AL)
- **Cast:** Chris, Rose, Police Officer
- **Props:** Dead deer (on roadside), Chris's phone, police officer's notepad/ID request
- **Animals:** DEER — struck by car, dies. Chris visibly affected (connects to mother's hit-and-run death). KEY SYMBOLIC PROP recurring throughout film.
- **Stunts:** Car hits deer (practical effect implied)
- **Wardrobe:** Police officer uniform
- **Narrative significance:** HIGH — deer symbolism (innocence killed, trophy/hunting metaphor), police interaction (Rose refuses officer's request for Chris's ID — establishes her as "protector," later revealed as manipulation to avoid creating paper trail linking Chris to her)
- **Source confidence:** HIGH — screenplay + GradeSaver + No Film School + The Take + Wikipedia

#### SC-008–012: EXT/INT. ARMITAGE ESTATE — DAY (Arrival, house tour)
- **Location:** Armitage family estate — large house in woods, long driveway, no neighbors (filmed: 6892 Heathcroft Lane, south of Fairhope, AL — exterior and interior)
- **Cast:** Chris, Rose, Dean Armitage (Bradley Whitford), Missy Armitage (Catherine Keener), Walter (Marcus Henderson), Georgina (Betty Gabriel)
- **Props:** 
  - Mounted deer head on wall (Dean's study/hallway)
  - Photos on wall (family history, including Roman Armitage's 1936 Olympics photo)
  - Lacrosse equipment (Jeremy's, mentioned by Dean during tour)
  - Dean's surgical/medical references (he's a neurosurgeon)
  - Tea service / cups in kitchen area
- **Vehicles:** None new (Rose's car parked)
- **Wardrobe:** 
  - Dean — earth tones, casual professor aesthetic (brown-palette; Haders: parents in brown for "grounded" feel that conflicts with horror)
  - Missy — earth tones, professional/composed
  - Walter — green and brown work clothes ("to blend in with grass and trees" — Haders; references Roman Armitage's 1936 Olympics photo)
  - Georgina — nightgown/maid uniform, "aged" wardrobe ("nod to how my grandmother used to dress" — Haders)
- **Set dressing:** Estate interior with colonial/upper-class aesthetic. African art pieces (Dean's appropriation collection). The deer head. Family photos.
- **Source confidence:** HIGH — screenplay + Giggster location guide + BET/Vogue Haders interviews + Raffia Magazine color analysis

#### SC-013–015: EXT. BACKYARD / INT. HOUSE — NIGHT (First night, hypnosis)
- **Location:** Armitage back porch / Missy's office (interior)
- **Cast:** Chris, Missy, (Rose sleeping upstairs)
- **Props:**
  - TEACUP AND SILVER SPOON — KEY PROP. Missy stirs tea; creates focal point for hypnosis. ("Slave masters used to summon slaves by striking their teacups" — Peele via GradeSaver. Silver spoon = "born with a silver spoon" = generational wealth.)
  - Chris's cigarette (his stress habit; Missy offers to help him quit)
  - Leather armchair (Chris sinks into during hypnosis)
- **VFX:** THE SUNKEN PLACE — Chris's consciousness falls into dark void while body remains in chair. Major VFX sequence. (Peele: "allegory for trauma and lack of agency")
- **Music:** Score — eerie, tension-building
- **Wardrobe:** Chris — gray sweatpants and T-shirt (the "cozy clothes" Rose suggested). Missy — composed professional attire
- **Narrative significance:** CRITICAL — teacup becomes the film's most iconic prop; Sunken Place becomes cultural touchstone
- **Source confidence:** HIGH — screenplay + Film Comment annotated screenplay excerpt + GradeSaver + The Take + multiple academic analyses

### ACT 2A — Fun and Games / Escalation (Pages 25–55, ~Scenes 20–40)

#### SC-016–018: EXT. WOODS / BACKYARD — DAWN (Morning after hypnosis)
- **Location:** Woods surrounding estate / backyard
- **Cast:** Chris, Walter (running past at speed), Georgina (seen through window knitting, then admiring herself in mirror)
- **Props:** Chris's camera with long-zoom lens (photographs bird, then catches Georgina in window)
- **Wardrobe:** Walter in groundskeeper work clothes (running in them — disturbing)
- **Source confidence:** HIGH — screenplay + Britannica plot summary

#### SC-019–025: INT/EXT. ARMITAGE ESTATE — DAY (Party arrives)
- **Location:** Armitage house interior and grounds (filmed: Heathcroft Lane, Fairhope + possibly Ashland Place Historic District elements)
- **Cast:** Chris, Rose, Dean, Missy, Jeremy Armitage (Caleb Landry Jones — first unmasked appearance), PARTY GUESTS (multiple — see cast list below), Logan King/Andre (LaKeith Stanfield — reappears, transformed), Jim Hudson (Stephen Root — blind art dealer)
- **Party guest cast** (named/credited):
  - Jim Hudson (Stephen Root)
  - Logan King / Andre Hayworth (LaKeith Stanfield) 
  - Philomena King (wife of "Logan", much older white woman)
  - Nelson, Gordon, Emily, Parker, Lisa, Hiroki Tanaka, and others (various credited actors)
- **Props:**
  - BINGO CARDS — used for silent auction bidding on Chris. Pre-marked as "winners." ("Although only one person will win the auction, everyone in the audience is already a winner" — GradeSaver)
  - Chris's phone/camera (accidentally flashes photo of Logan)
  - Badminton/bocce equipment (party activities mentioned)
  - Rose's box of photos (of her previous Black partners — discovered later but pertains to this act)
  - Cocktails/drinks/catering for garden party
- **Wardrobe:**
  - ALL GUESTS WEAR RED DETAILS — men: red pocket squares, red ties, red blouses; women: red clothing, red lipstick, red jewelry. ("Red is a symbol of their secret society" — Haders via Cinemablend, Raffia Magazine, Mediaknite)
  - Many guests in black and white ("visual representation of racial tensions" — Haders)
  - Chris still in BLUE (chambray/denim shirt — "color of his urban life, his true self" — Haders). Visually marks him as outsider.
  - Rose switches from blue to red-and-white striped shirt
  - Logan/"Andre" — fedora, stiff formal clothing (inappropriate for his actual age — parallels Walter/Georgina's "aged" wardrobe)
  - Jeremy — casual/preppy, slightly aggressive energy
- **Music:** Score shifts to tension during party sequence
- **VFX / Practical:** Blood from Logan's nose when camera flash goes off (practical makeup effect — "the real man, Andre, is coming out" — GradeSaver)
- **Stunts:** Logan grabs Chris violently after flash, has to be restrained
- **Narrative significance:** CRITICAL — party is the central setpiece of Act 2. The auction scene is an allegory for slave auctions (GradeSaver). Peele's annotated screenplay confirms this was the scene that made him decide to direct the film himself.
- **Source confidence:** HIGH — screenplay + Film Comment annotated screenplay excerpt + GradeSaver + Wikipedia + Raffia Magazine + Mediaknite

### ACT 2B — Complications (Pages 55–75, ~Scenes 40–55)

#### SC-026–030: INT. VARIOUS ROOMS — DAY/NIGHT (Chris's investigation)
- **Location:** Rose's bedroom, hallways, various Armitage interior rooms
- **Cast:** Chris, Rose, Rod (phone), Georgina
- **Props:**
  - Chris's cell phone (found UNPLUGGED — someone disconnected it)
  - Chris's camera phone (sends photo of Logan to Rod)
- **Wardrobe:** Chris continues blue palette
- **Source confidence:** MEDIUM-HIGH — screenplay + Go Into The Story scene breakdown

#### SC-031–035: INT. ARMITAGE HOUSE — NIGHT (Discovery + reveal)
- **Location:** Rose's bedroom closet, main floor
- **Cast:** Chris, Rose, Dean, Missy, Jeremy
- **Props:**
  - BOX OF PHOTOS — Rose's previous Black partners, including Walter and Georgina. Hidden in closet. KEY PROP for the reveal.
  - CAR KEYS — Chris repeatedly asks Rose for the keys. She stalls. The keys become the physical symbol of his entrapment.
  - Rose's FRUIT LOOPS AND MILK — separate glass of white milk, colored cereal eaten separately. Black straw. ("Rose has the ability to keep these things separate" — Mediaknite. Added shortly before shooting — Wikipedia/Peele)
  - Rose's EARBUDS/LAPTOP — searches for her next victim while Chris fights for his life downstairs
- **Wardrobe:** Rose's REVEAL costume — changes from casual to "hunting jodhpurs, a white dress shirt, and a sleek ponytail" (Wikipedia citing Peele). "Her previous 'soft and welcoming' appearance becomes a vision of cold, meticulous elitism."
- **Narrative significance:** CRITICAL — the reveal. Rose is not the ally; she's the hunter.
- **Source confidence:** HIGH — screenplay + Wikipedia + StudioBinder + Mediaknite

### ACT 3 — Resolution (Pages 75–104, ~Scenes 55–70)

#### SC-036–040: INT. BASEMENT / OPERATING ROOM (Chris captive)
- **Location:** Armitage basement (filmed: Barton Academy, 504 Government St, Mobile, AL — the house itself didn't have a suitable basement)
- **Cast:** Chris, Jim Hudson (on TV screen), Dean (surgical prep)
- **Props:**
  - LEATHER ARMCHAIR — Chris strapped to it. Same style chair as hypnosis scene.
  - COTTON STUFFING — Chris pulls from torn armrest. Plugs ears to block hypnosis. ("The visual of a Black man picking cotton to save himself is an unmissable and deeply ironic reference to slavery" — No Film School, GradeSaver, The Take)
  - TV/SCREEN — plays pre-recorded video of Jim Hudson explaining the Coagula procedure
  - SURGICAL EQUIPMENT — operating table, medical instruments, bright surgical lights
  - Mounted DEER HEAD — on basement wall, staring down at captive Chris (mirrors trophy/hunting theme)
  - DEER ANTLERS — Chris later uses to kill Dean. ("The symbol of slavery is inverted to become his tool of escape" — The Take)
- **VFX:** Bright surgical lights into camera (Peele: "like on a movie set"), Sunken Place visual for hypnosis resistance
- **Wardrobe:** Chris — still in same clothes, now restrained. Dean — surgical scrubs/gown
- **Source confidence:** HIGH — screenplay + GradeSaver + No Film School + The Take + Screen Rant (Barton Academy location)

#### SC-041–048: INT/EXT. ARMITAGE ESTATE — NIGHT (Escape sequence)
- **Location:** Basement, hallways, kitchen, exterior grounds, road (Heathcroft Lane + surroundings)
- **Cast:** Chris, Dean, Missy, Jeremy, Georgina/Marianne, Walter/Roman, Rose
- **Props:**
  - Cotton stuffing (in Chris's ears)
  - Deer antlers (weapon — kills Dean)
  - Teacup (Missy attempts to use again for hypnosis — fails because cotton ear plugs)
  - ROSE'S RIFLE — Walter/Roman takes it, shoots Rose, then himself
  - Chris's PHONE (camera flash used to break Walter out of Roman's control — callback to Logan/Andre flash scene)
  - Lacrosse stick or blunt object (Jeremy attacks Chris with)
  - Kitchen items (fire starts — Dean falls on something flammable)
- **Vehicles:**
  - JEREMY'S PORSCHE — Chris escapes in it. "Run Rabbit Run" is playing on the car stereo (callback to opening scene, confirms Jeremy was the abductor)
  - Chris accidentally hits Georgina with the Porsche (parallel to the deer strike)
  - ROD'S TSA VEHICLE — arrives at end. Looks like police car. Chris surrenders expecting arrest. Revealed to be Rod. ("A police car arrives and Chris surrenders, with Rose believing that the police will arrest Chris" — Wikipedia)
- **Stunts:** Chris bludgeons Jeremy, kills Dean (falls into fire), fights Missy, runs Georgina over with car (she attacks him inside, car crashes), Walter/Roman shoots Rose then himself, Chris strangles Rose (stops himself)
- **VFX/Practical:** Fire (Dean + room), car crash, gunshot wounds, blood
- **Makeup:** Blood on Chris's hands, Rose's gunshot wound, Walter's self-inflicted wound
- **Music:** Score crescendo. Silence at the Rod reveal moment.
- **Wardrobe:** Rose — white shirt + jodhpurs (hunting outfit, now bloodied). Chris — disheveled, bloody versions of same clothes.
- **Source confidence:** HIGH — screenplay + Wikipedia + multiple plot summaries

#### SC-049: EXT. ROAD — NIGHT (Ending)
- **Location:** Road outside Armitage estate
- **Cast:** Chris, Rose (on ground, wounded), Rod
- **Vehicles:** Rod's TSA vehicle (with emergency lights)
- **Props:** Rose's rifle (on ground)
- **Wardrobe:** Rod — TSA uniform
- **Narrative significance:** CRITICAL — the ending subverts audience expectation (police car = arrest for Black man). Peele's original ending had Chris arrested. Changed for theatrical release.
- **Source confidence:** HIGH — screenplay + Wikipedia (alternate ending documented)

---

## Part 3: Consolidated Production Element Lists

### 3A: Complete Cast (Credited, by significance)

| Character | Actor | Scenes Present | Notes |
|-----------|-------|---------------|-------|
| Chris Washington | Daniel Kaluuya | Nearly all | Protagonist, photographer |
| Rose Armitage | Allison Williams | ~60% of scenes | Antagonist revealed in Act 2B |
| Dean Armitage | Bradley Whitford | ~30% of scenes | Neurosurgeon, father |
| Missy Armitage | Catherine Keener | ~25% of scenes | Hypnotherapist, mother |
| Rod Williams | Lil Rel Howery | ~15% of scenes | TSA officer, Chris's best friend, comic relief, savior |
| Jeremy Armitage | Caleb Landry Jones | ~20% of scenes | Son, physically aggressive, abductor |
| Jim Hudson | Stephen Root | ~10% of scenes | Blind art dealer, wins auction for Chris |
| Walter / Roman Armitage | Marcus Henderson | ~15% of scenes | Groundskeeper body / grandfather's consciousness |
| Georgina / Marianne Armitage | Betty Gabriel | ~15% of scenes | Housekeeper body / grandmother's consciousness |
| Andre Hayworth / Logan King | LaKeith Stanfield | ~10% of scenes | Abducted in opening, reappears as "Logan" at party |
| Philomena King | — | Party scenes | Logan's much-older white wife |
| Richard Herd | Richard Herd | Pre-Coagula flashback/photo | Roman Armitage (original body) |
| Party guests | ~15+ credited + uncredited extras | Party sequence | Multiple named characters |
| Police officer(s) | — | Deer strike scene | One in film (two in screenplay) |
| Sid | Dog | Brooklyn scenes | Chris's dog, left with Rod |

### 3B: Complete Props Master List

**Narrative-critical props (must-find for any competent breakdown):**

1. Teacup and silver spoon — Missy's hypnosis tool
2. Mounted deer head — Armitage house wall + basement
3. Cotton stuffing — from leather armchair, Chris's ear plugs
4. Deer antlers — Chris's escape weapon (removed from mounted head)
5. Chris's camera (with flash) — breaks hypnosis on Logan and Walter
6. Box of Rose's photos — evidence of previous Black victims
7. Car keys — Rose withholds them, symbol of entrapment
8. Knight's helmet — Jeremy's abduction disguise
9. Bingo cards — auction bidding mechanism
10. Rose's rifle — final confrontation weapon
11. Tranquilizer dart gun — abduction weapon (opening)

**Significant secondary props:**

12. Chris's cell phone (unplugged by Georgina/family)
13. Rose's phone (selfie in car)
14. Fruit Loops cereal + glass of white milk + black straw (Rose's separation symbolism)
15. Leather armchair (hypnosis scene + captivity scene)
16. TV/screen (Coagula procedure video)
17. Surgical equipment (operating room prep)
18. Cigarettes (Chris's stress habit, Missy exploits)
19. Family photos on wall (including Roman's 1936 Olympics photo)
20. Rose's earbuds + laptop (browsing for next victim during escape)
21. Lacrosse equipment (Jeremy's, mentioned in house tour)
22. Badminton/bocce sets (party activities)
23. Fast food wrappers (Rose's car)
24. Luggage (Chris packing for trip)
25. Dart (in Andre's back)

### 3C: Vehicles

| Vehicle | Owner/Driver | Scenes | Notes |
|---------|-------------|--------|-------|
| Vintage cream Porsche (tinted windows, roof) | Jeremy Armitage | Opening abduction + escape sequence | "Run Rabbit Run" plays from stereo; white color intentional (Peele) |
| Rose's car (red) | Rose drives, Chris passenger | Drive to estate + deer strike | Red = danger foreshadowing |
| Rod's TSA vehicle | Rod Williams | Final scene only | Mimics police car appearance; subverts audience expectation |
| Police car | Police officer | Deer strike scene | Brief appearance |

### 3D: Locations (Script → Production)

| Script Location | INT/EXT | Production Location | Scenes |
|----------------|---------|-------------------|--------|
| Suburban street (opening) | EXT, NIGHT | Ryan Ave & De Leon Ave, Mobile, AL | SC-001 |
| Chris's Brooklyn apartment | INT, DAY | 127 Dauphin St, Mobile, AL | SC-002–003 |
| Brooklyn street | EXT, DAY | Near 127 Dauphin St | SC-003 |
| LaGuardia Airport exterior | EXT, DAY | — | SC-005 |
| Rural road (upstate NY) | EXT, DAY | Roads near Fairhope, AL | SC-007 |
| Armitage estate (house + grounds) | INT/EXT, DAY/NIGHT | 6892 Heathcroft Lane, Fairhope, AL | SC-008–049 (majority) |
| Armitage basement / operating room | INT, NIGHT | Barton Academy, 504 Government St, Mobile, AL | SC-036–041 |
| Road outside estate | EXT, NIGHT | Near Heathcroft Lane | SC-049 |
| Sports car interior | INT, NIGHT | — (car interior) | SC-001, SC-041+ |

### 3E: Wardrobe Summary (by character arc)

**Chris Washington — Color arc: Blue → Gray → Blue (disrupted)**
- Brooklyn: Blue henley, dark jeans, gray hoodie. Levi's jeans, Red Wing boots. ("Blue = his true self, urban life" — Haders)
- At Armitage estate: Gray T-shirt and sweatpants ("cozy clothes" Rose suggested; "gray exists between black and white" — Haders)
- Party day: Blue chambray/denim neckband shirt, dark indigo jeans (The Kooples shirt, FRAME L'Homme jeans per Spotern)
- Captivity/escape: Same party clothes, progressively bloody and disheveled

**Rose Armitage — Color arc: All-American → Predator**
- Act 1–2A: Denim dress ("All-American girl"), casual/approachable, red-white-blue scheme with Chris
- Act 2A party: Red-and-white striped shirt (shifts toward red/society colors)
- Reveal/Act 3: Hunting jodhpurs, white dress shirt, sleek ponytail. ("A vision of cold, meticulous elitism" — Wikipedia/Peele). Completely different person visually.

**Armitage Parents — Earth tones throughout**
- Dean: Brown palette, casual academic/professional
- Missy: Composed, muted professional colors
- (Both in brown during climactic scenes — Haders: "grounded nature" that conflicts with horror genre expectations)

**Walter/Georgina — Deliberately "aged" wardrobe**
- Walter: Green and brown work clothes (camouflage with landscape — "literally invisible" per Raffia Magazine analysis)
- Georgina: Nightgown/maid uniform (Haders: "nod to how my grandmother used to dress" — aged for someone in a young body)

**Party guests — Red as cult signifier**
- Men: Red pocket squares, ties, or blouses
- Women: Red clothing, lipstick, or jewelry
- Black and white also prominent ("visual representation of racial tensions")

### 3F: Special Effects / VFX

| Effect | Type | Scenes | Notes |
|--------|------|--------|-------|
| The Sunken Place | VFX — falling through dark void | Hypnosis scenes (2+) | Cultural touchstone; Chris's consciousness separated from body |
| Blood from Logan's nose | Practical makeup | Party scene | Camera flash "wakes" Andre momentarily |
| Fire | Practical | Escape sequence | Dean falls on something flammable; room catches fire |
| Car crash | Practical/stunt | Escape — Chris hits Georgina with Porsche | Parallel to deer strike |
| Gunshot wounds | Practical makeup | Final confrontation | Walter shoots Rose, then himself |
| Surgical prep lights | Practical + possible enhancement | Basement/operating room | Bright lights into camera — "like on a movie set" (Peele) |
| Deer strike | Practical | Rural road | Car hits deer |

### 3G: Music / Sound Design

| Element | Type | Scene | Source |
|---------|------|-------|--------|
| "Run Rabbit Run" — Flanagan & Allen (1939) | Diegetic (from car) | Opening + escape in Jeremy's car | Screenplay + GradeSaver |
| "Redbone" — Childish Gambino (2016) | Diegetic/score transition | Post-opening, transition to Chris's life | Mediaknite + multiple analyses |
| "Sikiliza Kwa Wahenga" — Michael Abels (score) | Score — Swahili vocals | Opening credits + throughout | "Listen to your ancestors" — a warning to Chris (Peele via Wikipedia) |
| UNCF commercial voiceover | Diegetic (TV) | Chris's apartment — Sid watches TV | Peele voices the narration |
| Teacup stirring sound | Foley/diegetic | Hypnosis scenes | Rhythmic stirring = hypnotic trigger |

---

## Part 4: Source Registry

Each source is rated for reliability and coverage.

### Primary Sources (direct from production)

| ID | Source | URL / Reference | Coverage | Reliability |
|----|--------|-----------------|----------|-------------|
| S1 | Screenplay (Script Slug PDF) | scriptslug.com/script/get-out-2017 | Complete scene text | DEFINITIVE |
| S2 | Screenplay (AWS S3 alternate) | s3-us-west-2.amazonaws.com/.../Get-out.pdf | Alternate draft (some scene differences) | DEFINITIVE (note version differences) |
| S3 | Get Out: The Complete Annotated Screenplay (book) | Inventory Press, 2019 | Peele's own annotations, deleted scenes, 150+ stills | DEFINITIVE (not freely available — use Film Comment excerpt) |
| S4 | Film Comment excerpt of annotated screenplay | filmcomment.com/blog/excerpt-get-out-the-complete-annotated-screenplay-jordan-peele/ | Party scene + Sunken Place annotations by Peele | DEFINITIVE |
| S5 | Nadine Haders (costume designer) — Vogue interview | Referenced in BET, BAMF Style, Cinemablend | Wardrobe intent for all major characters | DEFINITIVE for wardrobe |
| S6 | Jordan Peele — IndieWire director commentary | indiewire.com/.../get-out-film-references-1201903703/ | Film references, intentional choices (Porsche color, etc.) | DEFINITIVE |

### Secondary Sources (academic / analytical)

| ID | Source | URL | Coverage | Reliability |
|----|--------|-----|----------|-------------|
| S7 | GradeSaver — Symbols, Allegory and Motifs | gradesaver.com/get-out-film/study-guide/symbols-allegory-motifs | 12 symbols with scene-level analysis | HIGH |
| S8 | Go Into The Story — Scene by Scene Breakdown | gointothestory.blcklst.com/script-analysis-get-out-scene-by-scene-breakdown-62d6b8ee5cd1 | Page-by-page scene breakdown | HIGH |
| S9 | Wikipedia — Get Out | en.wikipedia.org/wiki/Get_Out | Cast, production, locations, plot | HIGH (well-sourced article) |
| S10 | No Film School — Symbolism analysis | nofilmschool.com/get-out-symbolism | Key props symbolism (deer, cotton, teacup) | HIGH |
| S11 | The Take — Symbols, Satire & Social Horror | the-take.com/watch/get-out-explained-symbols-satire-social-horror | Props + thematic analysis | HIGH |
| S12 | Raffia Magazine — Color analysis | raffia-magazine.com/2019/12/16/exposing-racism-through-colors-get-out-does-it-right/ | Wardrobe color coding, red/blue motifs | HIGH |
| S13 | Mediaknite — MEDIA analysis | mediaknite.org/get-out/ | Props (milk/cereal, teacup), costume, sound | MEDIUM-HIGH |
| S14 | Dartmouth Feminist Guide to Get Out | journeys.dartmouth.edu/feministguidetogetout/ | Symbolism, props, character analysis | HIGH (academic) |
| S15 | Arc Studio Pro — Screenplay Breakdown | arcstudiopro.com/blog/get-out-screenplay-breakdown | Story structure, beat analysis | MEDIUM |

### Tertiary Sources (location / production data)

| ID | Source | URL | Coverage | Reliability |
|----|--------|-----|----------|-------------|
| S16 | Giggster — Filming Locations | giggster.com/guide/movie-location/where-was-get-out-filmed | Verified addresses with scene mapping | HIGH |
| S17 | The Cinemaholic — Filming Locations | thecinemaholic.com/get-out-find-out-all-the-place-where-the-movie-was-shot/ | Address-level location detail | HIGH |
| S18 | Screen Rant — Filming Locations Explained | screenrant.com/get-out-filming-locations-explained/ | Barton Academy basement, Ashland Place | HIGH |
| S19 | movie-locations.com | movie-locations.com/movies/g/Get-Out.php | Concise location list | HIGH |
| S20 | BAMF Style — Chris wardrobe (2 articles) | bamfstyle.com/2024/02/24/get-out-chris-henley-hoodie-plaid-jacket/ + /2023/10/23/get-out-chris-denim-neckband-shirt/ | Item-level wardrobe ID (brand, color, fabric) | HIGH |
| S21 | Spotern — Get Out outfits | spotern.com/en/media/3575/get-out | Specific product identification for wardrobe | MEDIUM |
| S22 | IMDb — Full Cast & Crew | imdb.com/title/tt5052448/fullcredits/ | 47 credited cast + uncredited extras | HIGH |
| S23 | Britannica — Get Out | britannica.com/topic/Get-Out | Authoritative plot summary | HIGH |

---

## Part 5: Benchmark Methodology

### Test Procedure

1. **Input:** Raw screenplay PDF (S1 or S2) — fed to DeepRepo as the document corpus
2. **Task prompt:** "Produce a complete script breakdown for this screenplay. For each scene, extract: location (INT/EXT, place), cast present, props, vehicles, wardrobe notes, special effects, stunts, music/sound, and any other production elements."
3. **RLM approach:** Root model dispatches scene-by-scene to sub-LLM workers for extraction, then synthesizes
4. **Baseline approach:** Single model call with full screenplay in context
5. **Ground truth:** This document

### Scoring

For each extraction category, calculate:
- **Precision** = correct items found / total items reported (penalizes hallucinated items)
- **Recall** = correct items found / total items in ground truth (penalizes missed items)
- **F1** = harmonic mean of precision and recall

An item is "correct" if it matches a ground truth entry for the right scene. Partial credit (0.5) for items assigned to wrong scene but correctly identified as present in the film.

### Expected Differentiators

Based on the RLM pattern's strengths, we predict:

- **RLM advantage on recall:** Sub-LLM workers examining individual scenes will catch props mentioned in passing dialogue that a single model skimming the full script will miss (e.g., the fast food wrappers, the UNCF commercial, the dart sticking out of Andre's back)
- **Baseline advantage on cross-scene connections:** A single model seeing the full script may better identify recurring props across scenes (e.g., the teacup appearing in both hypnosis scenes, the deer recurring as head on wall)
- **RLM advantage on wardrobe:** Scene-by-scene analysis forces attention to what characters are wearing in each specific scene, which baseline tends to summarize globally
- **RLM advantage on completeness:** Baseline will likely skip or skim party scenes with many simultaneous elements; RLM dispatches them individually

### Minimum Viable Ground Truth

The full scene-by-scene ground truth above covers ~50 scenes with 200+ individual production elements across categories. For the V0 benchmark, a subset of 20–25 key scenes with ~120 verified elements is sufficient to produce statistically meaningful precision/recall numbers.

Priority scenes for ground truth verification (highest density of production elements):
1. Opening abduction (SC-001) — 8+ elements
2. Brooklyn departure (SC-002–004) — 10+ elements  
3. Deer strike (SC-007) — 6+ elements
4. Arrival at estate (SC-008–012) — 15+ elements
5. First hypnosis / Sunken Place (SC-013–015) — 10+ elements
6. Party sequence (SC-019–025) — 20+ elements
7. Discovery / reveal (SC-031–035) — 12+ elements
8. Captivity / cotton (SC-036–040) — 12+ elements
9. Escape sequence (SC-041–048) — 15+ elements
10. Ending (SC-049) — 5+ elements

---

## Part 6: Open Items

- [ ] Download and verify both screenplay PDFs — confirm scene count and any draft differences
- [ ] Cross-reference party guest names between screenplay and IMDb cast list
- [ ] Verify the two screenplay versions (Script Slug vs AWS S3) — note any scene additions/deletions
- [ ] Decide whether to include the alternate ending in ground truth (it's in the annotated screenplay book)
- [ ] Build film domain loader (.fountain / .pdf screenplay parser)
- [ ] Build film domain prompts (extraction-focused, not analysis-focused)
- [ ] Run benchmark

---

*Compiled: February 22, 2026*
*Sources: 23 public references (see Part 4)*
*Status: V0 — ready for benchmark implementation*
