# 🎬 SignalDock Demo Script

Use this script to record a punchy, 2-minute demo of SignalDock.

---

## Scene 1: The Hook (0:00 - 0:20)
**Goal:** Show, don't just tell.
**Action:** Have the app open at `http://localhost:3000`.

**Voiceover:**
"This is SignalDock. It's an automation platform that runs locally on your PC. Think of it like Zapier, but for your actual hardware—CPU, Network, Clipboard, and Files."

---

## Scene 2: The Interface (0:20 - 0:40)
**Goal:** Show the visual editor.
**Action:**
1.  Click **New Pipeline** (+ button).
2.  Hover over the **Node Palette** on the left.
3.  Drag out a **Source Node** (e.g., `CPU Monitor`). or `Clipboard Monitor`.

**Voiceover:**
"The heart of SignalDock is this visual pipeline editor. On the left, I have my sources—things like Battery, Window Focus, or Microphone levels. I just drag them onto the infinite canvas."

---

## Scene 3: Building a Pipeline (LIVE) (0:40 - 1:10)
**Goal:** Prove it works in real-time.
**Action:**
1.  **Select Source:** Change the node to `Clipboard`.
2.  **Add Action:** Drag an `Action Node` and select `Notification`.
3.  **Connect:** Draw a line from `Clipboard` output to `Notification` input.
4.  **Configure Action:**
    *   **Title:** "New Copy!"
    *   **Message:** "You copied: {{content}}"
5.  **Hit Save.**

**Voiceover:**
"Let's build a simple 'Clipboard Spy'. I'll take the Clipboard Source and connect it to a System Notification. I'll configure the message to show me exactly what I copied. Save... and it's live."

**Action:** Select some text in the script and copy it (Ctrl+C). Wait for the toast notification.

**Voiceover:**
"Boom. Instant local feedback."

---

## Scene 4: "Under the Hood" (The Matrix Moment) (1:10 - 1:40)
**Goal:** Show technical depth.
**Action:**
1.  Open VS Code / Terminal.
2.  Run: `python backend/test_sources.py`
3.  Let the text scroll for a few seconds.

**Voiceover:**
"For developers, SignalDock provides direct access to the signal stream. Here you can see the backend engine processing CPU stats, RAM usage, and network traffic in real-time, with zero latency."

---

## Scene 5: Outro (1:40 - 2:00)
**Goal:** Call to action.
**Action:** Switch back to the GitHub README (rendered view).

**Voiceover:**
"SignalDock is open source, built with Python and Next.js, and privacy-focused by design. Check out the repo to build your own local automations today."

---

## Preparation Checklist
- [ ] Backend running (`python main.py`)
- [ ] Frontend running (`npm run dev`)
- [ ] Terminal cleared for "The Matrix" scene
- [ ] Notifications enabled in Windows Focus Assist
