# Compass — Live Decision UX Revamp (implementation spec)

**Audience for the screen:** a demand planner who knows their job (deciding how
many units to commit) but is **not** a data scientist. They should be able to
read every line out loud and understand it, the text must be comfortably
readable, and the page must guide them top-to-bottom in clear numbered steps.

**Files you will edit**
- `app/views/live_decision.py` — all view copy, the `VIEW_CSS` constant (font sizes), helpers.
- `app/main.py` — `LIGHT_VIEW_OVERRIDES` constant (light-mode colours only; sizes live in VIEW_CSS).

**Do the parts in order. Part 0 is a correctness fix — do it first.**
**After each part, restart the app (`streamlit run app/main.py`) and eyeball it.**

---

## PART 0 — Fix the month-alignment bug (data correctness)

**Problem:** the page labels the planning period as next month (e.g. *Jul 2026*),
but `_get_machine_value()` resolves the model value from a different month
(it tries offsets `[1, 0, -1, -2]` and for "today = June" lands on *June 2026*).
The "same month last year" comparison then uses the *label* month (Jul 2025)
instead of the month the model value actually represents (Jun 2025). This makes
the headline comparison apples-to-oranges.

**Fix:** make `_get_machine_value` report which month it resolved, and use that
single month everywhere (label, last-year comparison, cycle label).

1. In `app/views/live_decision.py`, change `_get_machine_value` to **return a
   tuple** `(machine_value, resolved_month)` where `resolved_month` is a
   `"YYYY-MM"` string for the month it actually matched (or the planning period
   string if it fell back to the constant). Update the early-return and the
   final fallback accordingly.

2. In `render()`, update the call:
   ```python
   machine_value, machine_month = _get_machine_value(product_id, sales_org_id, channel_id)
   ```

3. Use `machine_month` (not `_planning_period()`) for:
   - the **Planning period** context box value,
   - the `cycle_label` (format `machine_month` → e.g. "Jun 2026"),
   - the `target_month` argument passed to `_decision_facts(...)`.

   Keep `_planning_period()` only if it is still used elsewhere; otherwise it can
   stay unused.

4. Result to verify: for CP-0271 / SO04 / CH01 the page should show the model
   value (~833) labelled **Jun 2026**, and "Same month last year" should read
   **Jun 2025 ≈ 1,605** (not 1,051). The headline gap vs last year becomes
   "~48% below last year", which is correct and a stronger story.

**Note on the run-rate gap (not a bug — leave as is, just confirm the wording):**
the recent run-rate (~1,240/mo) is correctly single-channel. The model forecasts
a decline, so the gap is real. The banner wording already says "the recent
run-rate" — keep that phrasing so it reads as an average, not a single month.

---

## PART 1 — Plain language (replace jargon)

Replace every left-hand string with the right-hand string. Match the existing
string exactly (including surrounding tags) and change only the human text.
Do **not** rename Python variables or CSS classes.

### Hero (top of `render()`)
- **"Review and defend the commitment"** → **"How many units should we commit for next month?"**
- **"Review the forecast, add your business insight, and make the final call with support from five specialist agents."**
  → **"Start with the system's forecast, adjust it using what you know about the market, then confirm the final number. A few automatic checks back you up along the way."**

### Context boxes
- Label **"Business unit"** → keep.
- Label **"Planning period"** → keep (value now comes from `machine_month`, Part 0).

### Story banner (`_build_story_line` + the banner block)
- Eyebrow **"The situation"** → **"What you're looking at"**
- Foot **"Add what you know that the model can't see, then commit with the panel's support."**
  → **"Add what you know that the forecast can't see, then confirm your number below."**
- In `_build_story_line`, change **"the model expects"** → **"the system forecasts"**, and
  **"committed revenue"** → **"in sales value"**. Keep the numbers/structure.

### Forecast snapshot (left column)
- Eyebrow **"Forecast snapshot"** → **"The starting number"**
- Heading **"What the model expects this cycle"** → **"What the system predicts for next month"**
- Badge **"● Model outlook"** → **"● System forecast"**
- Body message **"Compared against what this product has actually been selling, so you can see where the model sits before you commit."**
  → **"Shown next to what this product has actually been selling, so you can see how the forecast compares before you decide."**
- Mini-card labels: **"Recent run-rate"** → **"Recent monthly sales"**;
  **"Same month last year"** → keep; **"Value per unit"** → **"Sales value per unit"**;
  **"Stock on hand"** → **"Units in stock"**.
- In the mini-card notes, replace **"Model is X% below/above this"** → **"Forecast is X% below/above this"**.

### Planner judgment (right column)
- Eyebrow **"Planner judgment"** → **"Your decision"**
- Title **"Set the proposed commitment"** → **"Set the number you want to commit"**
- Slider label **"Planner override"** → **"Your proposed units"**
- Number input label **"Units"** → keep.
- Difference line **"{x}% versus machine forecast"** → **"{x}% higher/lower than the forecast"**
  (compute the word: if `difference_pct >= 0` use "higher than", else "lower than", and show `abs(difference_pct)`).
- Reason textarea label **"What does the planner know that the model does not? *"**
  → **"Why are you changing it? What do you know that the forecast doesn't? *"**
- Button **"Ask Compass to Review"** → **"Check my decision"**

### "What Compass found" section
- Heading **"## What Compass found"** → **"## What the checks found"**
- The lead line wording: replace **"signals point to"** → **"checks point to"**,
  and **"than the model"** → **"than the forecast"**.
- Push-chip labels in `_push_direction`: **"Points to stronger demand"** →
  **"Suggests higher demand"**; **"Points to softer demand"** → **"Suggests lower demand"**;
  **"Broadly neutral"** → keep.

### Compass Recommendation card
- Eyebrow **"Compass Recommendation"** → **"Suggested number"**
- Label **"Machine forecast"** → **"System forecast"**
- Label **"Planner proposal"** → **"Your proposal"**
- Label **"Compass recommends"** → **"Suggested"**
- Pills **"{x} vs machine"** → **"{x} vs forecast"**; **"{x} vs planner"** → **"{x} vs your number"**;
  **"{n} evidence signals"** → **"{n} checks run"**.
- Footer **"Recommendation only — the human still decides."** → **"This is only a suggestion — you make the final call."**

### Memory expander
- Title **"Memory and track record"** → **"How similar past decisions turned out"**
- Metric labels: **"Average planner FVA"** → **"Avg. accuracy gain"**;
  **"Reason-type average FVA"** → **"Avg. accuracy gain (this reason)"**;
  **"Reason-type calibration"** heading → **"What usually happens for this kind of reason"**.
- **"Calibrated suggestion from scored memory: N units"** → **"Based on similar past cases, a number near N has worked well."**

### Human final decision + Passport
- Heading **"## Human final decision"** → **"## Your final decision"**
- Radio label **"Choose how to commit"** → **"Pick your final number"**
- Radio options: **"Accept Compass recommendation"** → **"Use the suggested number"**;
  **"Keep my original override"** → **"Keep my own number"**;
  **"Enter another value"** → **"Type a different number"**.
- **"Final human commitment"** → **"Your committed number"**;
  **"units · Human approval required"** → **"units · you approved this"**.
- Button **"Commit Final Decision"** → **"Confirm and save"**
- Passport eyebrow **"Commitment Passport"** → **"Decision record"**
- **"Human approved"** → **"Saved"**; pill **"● Awaiting actuals"** → **"● Waiting for real sales"**
- Passport detail labels: **"Reason class:"** → **"Reason type:"** (and render the value with
  underscores replaced by spaces, e.g. `competitor_exit` → "competitor exit");
  **"Evidence signals:"** → **"Checks run:"**; **remove the "Backend mode:" line entirely**
  (internal detail, not for the planner).
- Closing paragraph **"This decision is now captured for future learning. When actuals arrive, Compass can compare machine error with final-decision error and calculate Forecast Value Added."**
  → **"This decision is saved. Once real sales come in, Compass measures how much your decision improved on the system's forecast."**

> Rule of thumb for any string you are unsure about: avoid the words
> **machine, override, planner (as a noun), agent, signal, FVA, reconciler,
> commitment** in user-facing copy. Prefer: **forecast/system, your number,
> you, assistant/check, accuracy, suggestion, commit (verb).**

---

## PART 1B — Voice: talk TO the planner, not ABOUT them (complete sweep)

The screen currently refers to the user in **third person** ("the planner",
"the human", "Human approval required"). Everything the user reads should be in
**second person ("you / your")**. This is a full list of the remaining
third-person / "the model" spots with line numbers (as of the current file) so
none are missed. Some overlap with Part 1 — if already changed there, skip.

### Third person → second person (user-visible text)
| ~Line | Current visible text | Replace with |
|---|---|---|
| 1413 | passport cell label **"Planner"** | **"Your number"** |
| 1429 | **"Planner:"** `{decision_maker}` | **"Decision by:"** `{decision_maker}` |
| 1516 | input label **"Planner ID"** | **"Your name or ID"** |
| 1794 | error **"Enter a valid planner override greater than zero."** | **"Enter a number greater than zero."** |
| 1796 | error **"Enter the planner's business reason before analysis."** | **"Add your reason before running the checks."** |
| 1798 | error **"Enter a planner ID before analysis."** | **"Enter your name or ID before running the checks."** |

(The other "planner/human" hits — `Planner judgment`, `Planner override`,
`Planner proposal`, `vs planner`, `Human final decision`, `Final human
commitment`, `Human approval required`, `Human approved`, the reason textarea,
the "the human still decides" footer, and `Average planner FVA` — are already
covered in Part 1. Verify each is done.)

### Leftover "the model" → "the forecast" (Part 1 missed these)
| ~Line | Current | Replace with |
|---|---|---|
| 1584 | story foot "...the model can't see, then commit with the panel's support." | "...the forecast can't see, then confirm your number below." (same as Part 1) |
| 1602 | mini-note **"In line with the model"** | **"In line with the forecast"** |
| 1615 | mini-note **"Similar to the model"** | **"Similar to the forecast"** |
| 1626 | mini-note **"≈ {x} at the model forecast"** | **"≈ {x} at the forecast"** |
| 1755 | consequence **"Matched to the model."** | **"Matched to the forecast."** |
| 1764–1771 | consequence **"below/above the model"**, **"demand lands near the model"** | **"below/above the forecast"**, **"demand lands near the forecast"** |

### Demo-mode card text (`run_pipeline_stub`, shown when no API key)
These appear as visible card/table text in demo mode — convert them too:
| ~Line | Current | Replace with |
|---|---|---|
| 586 | "...exceed the planner's proposed commitment of 360 units." | "...exceed your proposed number of 360 units." |
| 658 | evidence scenario **"Planner override"** | **"Your number"** |
| 704 | "...than the planner's proposed reduction." | "...than the reduction you proposed." |
| 773 | rationale "...versus the planner's proposed {x}." | "...versus your proposed {x}." |

> Leave Python identifiers, CSS class names (`.planner`, `planner-tone`),
> session-state keys (`planner_override`), and code comments unchanged — only
> change text the user actually sees on screen.

---

## PART 2 — Font sizes & readability

All these selectors are in the `VIEW_CSS` string inside `app/views/live_decision.py`.
Sizes there apply in **both** light and dark mode (the light overrides only change
colours), so you only edit them once. Change `font-size` (and `line-height`/
`min-height` where noted). Leave everything else in each rule unchanged.

| Selector | Current | New |
|---|---|---|
| `.eyebrow` | `.68rem` | `.76rem` |
| `.hero-copy, .muted-copy` | `.9rem` | `1rem` |
| `.context-label, .value-label` | `.63rem` | `.74rem` |
| `.context-value` | `.82rem` | `.95rem` |
| `.forecast-heading` | `1rem` | `1.1rem` |
| `.forecast-badge` | `.62rem` | `.72rem` |
| `.forecast-unit` | `.78rem` | `.9rem` |
| `.forecast-message` | `.78rem` (lh 1.55) | `.92rem` (lh 1.6) |
| `.forecast-mini-label` | `.58rem` | `.72rem` |
| `.forecast-mini-value` | `.92rem` | `1.05rem` |
| `.forecast-mini-note` | `.62rem` | `.76rem` |
| `.card-title` | `1.05rem` | `1.18rem` |
| `.card-copy` | `.78rem` | `.92rem` |
| `.signal-name` | `1.02rem` | `1.12rem` |
| `.signal-claim` | `.79rem` (lh 1.58, min-height 64px) | `.94rem` (lh 1.62, min-height 72px) |
| `.signal-friendly-meta` | `.66rem` | `.78rem` |
| `.mode-pill, .direction-pill` | `.62rem` | `.72rem` |
| `.push-chip` | `.6rem` | `.74rem` |
| `.story-line` | `1.02rem` | `1.15rem` |
| `.story-foot` | `.72rem` | `.84rem` |
| `.consequence` | `.74rem` (lh 1.5) | `.88rem` (lh 1.55) |

**Inline font sizes (these are in `style="..."` inside the markdown f-strings, not in VIEW_CSS — search and bump each):**
- Recommendation card: the `units · {confidence} confidence` line `font-size:.71rem` → `.82rem`;
  the rationale block `font-size:.81rem` → `.94rem`; the footer `font-size:.7rem` → `.8rem`.
- Difference line under the slider: `font-size:.82rem` → `.92rem`.
- Final commitment caption `font-size:.72rem` → `.82rem`.
- Passport: the detail block `font-size:.78rem` → `.9rem`; the decision-id line
  `font-size:.76rem` → `.84rem`; the closing note `font-size:.72rem` → `.82rem`;
  the four passport-cell numbers `font-size:1.65rem` → `1.8rem`.

Do **not** shrink the big hero/forecast/recommendation numbers — they are fine.

---

## PART 3 — Reading flow (numbered steps)

Goal: the planner reads the page as **4 clear steps**, top to bottom.

### 3a. Add a step-header component to `VIEW_CSS`
Add this block (plain CSS, no `.format`):
```css
.step-header { display:flex; align-items:flex-start; gap:.7rem; margin:1.6rem 0 .8rem; }
.step-num {
    flex:none; width:32px; height:32px; border-radius:50%;
    display:inline-flex; align-items:center; justify-content:center;
    font-size:1rem; font-weight:800; color:#0B1220;
    background:linear-gradient(135deg,#78DDF7,#B295FF);
}
.step-text { display:flex; flex-direction:column; }
.step-title { font-size:1.4rem; font-weight:800; color:#F4F7FB; line-height:1.15; letter-spacing:-.02em; }
.step-sub { font-size:.9rem; color:#9AA8BC; margin-top:.15rem; }
```
Add light-mode colours to `LIGHT_VIEW_OVERRIDES` in `app/main.py`:
```css
.step-title { color:#0d1b2e !important; }
.step-sub { color:#4d6278 !important; }
.step-num { color:#0B1220 !important; }
```

Add a small Python helper near the other render helpers:
```python
def _step_header(number: int, title: str, subtitle: str) -> None:
    st.markdown(
        f'''<div class="step-header">
            <div class="step-num">{number}</div>
            <div class="step-text">
                <div class="step-title">{html.escape(title)}</div>
                <div class="step-sub">{html.escape(subtitle)}</div>
            </div>
        </div>''',
        unsafe_allow_html=True,
    )
```

### 3b. Place the step headers (in `render()`)
- **Before the selectors** (product/org/channel/planner row):
  `_step_header(1, "Pick what you're planning", "Choose the product, region and channel for this decision.")`
- **Before the `left, right = st.columns(...)` row** (so it sits above the
  forecast snapshot + your-decision columns; the story banner stays just above it):
  `_step_header(2, "Understand the forecast and set your number", "On the left: what the system predicts and how it compares to real sales. On the right: enter the number you want to commit and why.")`
- **Replace `st.markdown("## What Compass found")`** (already being renamed in Part 1) with:
  `_step_header(3, "See what the checks found", "Independent checks of your number against demand, supply, finance, market and past decisions.")`
  (Delete the old `##` heading line; the step header replaces it. Keep the lead line that follows.)
- **Replace `st.markdown("## Human final decision")`** with:
  `_step_header(4, "Confirm and commit", "Pick your final number and save the decision.")`

### 3c. Tag the two columns
- At the top of the **left** column (above the forecast card) add a tiny tag line:
  `st.caption("① The system's forecast")` — or reuse the eyebrow already inside the card.
- At the top of the **right** column, the eyebrow is already "Your decision" (Part 1).
  Leave as is. The point is the left = reference, right = action.

### 3d. Compact the context boxes (optional but recommended)
The 5 context boxes are reference detail, not the main story. Reduce visual
weight: in `.context-box` change `min-height: 74px;` → `min-height: 60px;` and
`padding: .78rem .85rem;` → `padding: .6rem .7rem;`. This lets the eye reach the
story banner and Step 2 faster. (Colour/feel unchanged.)

---

## PART 4 — Verification checklist

Run `streamlit run app/main.py`, open the Live Decision view, and confirm:
1. Planning period reads **Jun 2026** and "Same month last year" reads **≈1,605** for CP-0271/SO04/CH01 (Part 0).
2. No user-facing text contains: machine, override, agent, signal, FVA, reconciler, "commitment" as a noun (Part 1).
2b. No user-facing text says "the planner", "the human", or "the model" — it reads as "you / your / the forecast" (Part 1B). Check the consequence box, the passport, the field labels, and the validation errors specifically.
3. Every label and body line is comfortably readable at normal zoom (Part 2).
4. Four numbered step circles appear top-to-bottom, and reading them in order tells a complete story (Part 3).
5. Toggle to **light mode** and re-check: step headers, banner, chips and consequence box all have correct (not dark-on-light) colours.
6. Switch product to one with no history (e.g. **PC-0029 / SO04 / CH01**): cards
   should read "Not available" gracefully, no crash.
