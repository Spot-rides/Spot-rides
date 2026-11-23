# Spot Rides landing page

Landing page for **Spot Rides**, a ride-sharing pilot for verified college students in Hyderabad. Students on the same route share bike or car rides and split fuel at ₹3 per km.

It's a single static page: plain HTML, CSS and a little vanilla JS, with no build step.

## Files

| File | What it is |
| --- | --- |
| `index.html` | The whole page (styles and script inline) |
| `favicon.svg` | Browser tab icon |

## Run locally

Open `index.html` in a browser, or serve the folder:

```bash
npx serve .
# or
python -m http.server 8000
```

## Deploy

Any static host works. No build command is needed, and the output directory is the repo root.

- **Vercel:** import the repo, framework preset "Other".
- **Netlify:** drag the folder onto app.netlify.com/drop, or connect the repo.
- **Cloudflare Pages / GitHub Pages:** point it at the `main` branch root.

## Things to update

- **Sign-up link:** every "Join the pilot" button points to the Google Form. Search `docs.google.com/forms` in `index.html` to change it.
- **Pilot colleges:** the FAQ says "our pilot colleges in Hyderabad". Add the names once confirmed.
- **Privacy policy and terms:** short starter text in the footer. Review it before launch.
- **Social preview image:** add an `og:image` (1200×630) so WhatsApp link previews show a picture.
- **Analytics:** add Microsoft Clarity or GA4, and use tagged links (`?utm_source=whatsapp&utm_campaign=<college>`) to see which channel brings sign-ups.
