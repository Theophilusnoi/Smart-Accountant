# SPEC: Smart Accountant promo

GOAL:    the viewer understands that a paper invoice becomes a booked, categorised transaction without typing, and wants the free demo.
OUTPUT:  HyperFrames, 1920 x 1080, 30 fps
TIME:    25.0 s x 30 = 750 frames. No music (none available in this session).

LOOK:
- Desk world: ground #D8D2C4 flat laminate; paper #FFFFFF, shadow 0 18px 44px rgba(40,30,10,.22); ink #1F2937.
- Product world (the app's Tailwind palette): ground #F9FAFB (gray-50), cards #FFFFFF with 1px #E5E7EB border and 0 2px 6px rgba(0,0,0,.06),
  ink #111827, secondary #4B5563, primary #2563EB, active fill #EFF6FF, success #16A34A, expense #DC2626.
- Brand: gradient #2563EB -> #9333EA (the app's logo badge and Home CTA section). Allowed only on: the logo badge, the claim ground, "AI-Powered", the CTA button.
- Type: Inter (the app uses the system sans; Inter is the nearest bundled face). Titles 700 at 84 px, -2% tracking; claim number 900 at 300 px;
  UI scaled ~1.6x from the web app, nothing readable under 28 px.
- Depth: paper shadows only; no grain, no vignette, no glow.

OBJECTS:
- The invoice: white sheet 600 x 780, "INVOICE", vendor ABC Office Supplies, INV-2025-001, 2025-01-10, line "Office supplies and stationery" $234.50, total.
- The cursor: black arrow with white outline, 60 px tall (5.5% of frame), enters from off-screen.
- Product screens: Upload Invoice, Data Extracted Successfully, Dashboard -> Recent Transactions, rebuilt from the JSX with real labels and values.

MOTION:
- enter: expo.out / power4.out; camera and floods: power2.inOut; exits and zoom-through: power3.in.
- titles: per-word blur 6px -> 0 in 0.13 s, 0.067 s apart, no translate; exits blur-out 0.15 s.
- logo: elastic.out(1, 0.75) (damping ~0.75) on position only.
- motion blur on (data-motion-blur) for the drops, carry and whip.

SHOTS (global time):
- 0.0-6.0 desk: invoice on desk at frame 0; "Another invoice to type in" (0.15); 6 invoices drop behind it (1.8-2.9); "And another. And another." (2.2);
  cursor grabs it (3.6-4.3); "What if it read itself?" (4.1); carry + flood to gray-50 (5.0-5.7), invoice shrinks into the drop-zone position.
- 6.0-13.4 upload: UI builds round the carried invoice (0.0-0.5); drop (0.9); Processing 0->100% (1.2-3.4); camera pans to
  Data Extracted Successfully (3.5-4.1); fields fill (4.2-5.45); 95% Confidence pops (5.8); cursor clicks Save Invoice (6.9).
- 12.95-16.85 dashboard: iris opens from the Save click (0.35 s); push-in to Recent Transactions (1.0-1.6); the $234.50 row inserts at top (1.7-2.3); hold; whip left (3.6-3.9).
- 16.7-25.0 claim + end: gradient whips in; "90%" counts up, "less manual data entry"; hold; flood to white; mark drops in, wordmark wipes,
  "Next-Generation AI-Powered Accounting Software", START MY FREE DEMO holds 2.6 s.

BANNED: dark void ground; glow/particles/glass; purple-blue gradients outside the brand uses above; fading-and-sliding-up entrances;
three cards in a row as a feature list; title over dimmed screenshot; docked logo; moving titles after they land; invented dashboard values;
the stock dashboard/robot images in src/assets (not the product).

QA: t=0.0 (thumbnail: invoice + title), 2.6 (pile), 5.4 (carry mid), 6.4 (UI built round invoice), 8.5 (progress), 11.7 (fields + badge),
13.1 (iris mid), 15.0 (new row), 18.5 (claim), 23.5 (end card).
