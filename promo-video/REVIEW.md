# Review: Smart Accountant promo (v1)

Output: `renders/smart-accountant-promo.mp4`, 25.0 s, 1920x1080, 30 fps, H.264, silent.

## Creative calls
- Built storyline A "One invoice, start to books" (see STORYLINES.md). Not built: B (trial balance: the app's
  sample data is unbalanced, $37,034.49 vs $48,500) and C (before/after split screen).
- Product name shown as "Smart Accountant" (repo name, as requested). The app code says "AI Accountant";
  the name is a variable (`brand-name`) in each scene for an easy swap.
- Every screen is rebuilt from the app's JSX with its real labels and sample values. The stock images in
  `src/assets` (crypto dashboard, robot, illustration) were left out because they are not the product.
- The saved invoice appears in Recent Transactions as "ABC Office Supplies" (the extracted vendor); the app's own
  sample row for the same $234.50 / 2025-01-10 / Office Expenses expense reads "Office Supplies - Staples".
- "Welcome back!" stands in for the app's `Welcome back, {first_name}!`.
- Claim "90% less manual data entry" comes from Home.jsx ("reduce manual data entry by 90%").
- Font: Inter (nearest bundled face to the app's system sans).

## Measured vs looked at
- `hyperframes check`: passes, 0 errors.
- Looked at: snapshot contact sheets at 10 QA times, the review seams (desk->upload, dashboard->endcard),
  and 7 frames pulled from the rendered MP4.
- Sound: none. Music needs a HeyGen sign-in (`npx hyperframes auth login`), which this session does not have.

## Warnings kept on purpose
- `film_silent`: no music source available.
- `line_unread` (dashboard metric cards, subtitle, Outstanding Invoices): a 1 s establishing shot before the
  camera pushes into Recent Transactions; the viewer is not meant to read them.
- `first_frame_empty`: false positive; frame 0 shows the invoice on the desk (the invoice carries
  `data-layout-ignore` because it shrinks below the type floor while carried).

## Weakest shot, and next steps
- The dashboard payoff is quiet: the row lands with no number changing. With more time: let Total Expenses
  tick by $234.50, or pull back to show the row in the whole dashboard.
- Add a music bed (open on the product reveal at 6 s), a click on Save Invoice, and a pop on 95% Confidence.
