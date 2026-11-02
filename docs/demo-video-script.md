# Swayam-sevak: demo video script (3 speakers, about 3.5 minutes)

Record live on https://anurag137-swayam-sevak.hf.space. Open it 5 minutes early so it is awake.
Speakers: **A** (intro + Part 1), **B** (Part 2), **C** (Part 3 + close). Keep the screen on the app the whole time.

---

## 0:00 – 0:25 · Intro: Speaker A
**Screen:** home page with live news.

**A:** "Hi, we're [team name]. Every year crores of Indians miss benefits they are entitled to, because the rules are in long English PDFs and the portals are hard to use. We built **Swayam-sevak**, a civic assistant that does three things. It explains official documents in your language, lets you report civic problems that the public can track, and has an agent that actually works on government portals for you, always with your approval. Everything you'll see is running live right now."

## 0:25 – 1:20 · Part 1, document explainer: Speaker A
**Screen:** Explainer. Paste a real .gov.in link (e.g. the PMSBY rules PDF), choose **Hindi** or **Telugu**, press Explain.

**A:** "Here I paste a real scheme document from a government website and ask for Hindi. It reads the PDF, even scanned pages, and explains who is eligible, how much it costs and how to apply."
*(Result appears.)*
"Notice every point has a quote and a page number from the original document. Our code checks that each quote really exists in the document. If it doesn't, the point is removed, so the AI can't invent rules."
*(Click the speaker icon, or ask a question by voice.)*
"It can also read the answer aloud, and I can ask a follow-up by voice in my own language. It works in 12 Indian languages."

## 1:20 – 2:10 · Part 2, civic reports and public board: Speaker B
**Screen:** Report a problem → fill a real issue (photo, location) → submit → open **/board**.

**B:** "Now civic problems. A citizen reports a problem with a photo and location. The system sorts it by category and urgency, finds the ward and sets a deadline for resolution."
*(Open the board.)*
"Every report appears on this public board, so anyone can see what's open, what's resolved and what's overdue. The one sample here is clearly labelled as ours, to show the workflow. We don't use fake data. Photos stay private and are served only through our server, and when an officer fixes the problem they upload proof that the public can see."

## 2:10 – 3:15 · Part 3, the assisted agent: Speaker C
**Screen:** Agent console. Type: "Which schemes am I eligible for? I'm a 45-year-old woman farmer in Maharashtra."

**C:** "Finally, the agent. I ask in plain language which schemes I'm eligible for. It opens a real browser on the official myScheme portal, and you can watch every step live, with its reasoning."
*(Steps stream in.)*
"Once a task has worked, it's saved as a route, so next time it replays in seconds."
*(Optional: type "book a train ticket for me". It refuses.)*
"And it has hard limits written in code, not just instructions to the AI. It only visits allow-listed government sites and only types what you told it. Your private details stay in an encrypted vault the AI never sees, OTPs and CAPTCHAs are handed back to you, and nothing is submitted until you approve. It never presses Pay."

## 3:15 – 3:35 · Close: Speaker C (or all three)
**Screen:** back to the home page / GitHub README.

**C:** "Swayam-sevak: grounded in official sources, honest about what it doesn't know, and a person approves every submission. The code is open on GitHub, and the link is in our submission. Thank you!"

---

### Tips
- Do one practice run first; the agent step can take 10–30 seconds. Talk over it, and don't cut it out.
- Don't speed up or edit the footage to fake results. Live means live.
- Use a real issue you've seen for Part 2, not a made-up one.
- Never show `.env`, the Hugging Face Settings page or any API key on screen.
