# WhatsApp message templates (drafts for Meta submission)

Status: **DRAFT, not yet submitted**. Until each one is approved, code sends them only through the fake adapter.
Meta decides the final category. Our guess is noted against each template.

Format rules we kept to (TO VERIFY against the current Meta template guidelines):
- Variables are positional `{{1}}`, `{{2}}` …, never at the very start or end of the body, never two side by side.
- Body ≤ 1024 characters, header ≤ 60, footer ≤ 60, quick-reply button text ≤ 25.
- No fees, results or rankings in templates. Those facts only appear in free-form replies, inside the 24-hour window, taken from the verified KB.
- Every parent-facing template has a "Stop messages" quick reply (opt-out).
- Sample values are fake.

Language codes: `en`, `hi`. Template names are the same across languages; the language code selects the version.

---

## 1. `enquiry_first_response`: first reply to a new enquiry
- Category: **MARKETING** (likely; could be UTILITY because it answers the parent's own form). Recipient: parent.
- Variables: `{{1}}` parent name, `{{2}}` school name, `{{3}}` grade.
- Buttons (quick reply): `Book a campus visit` · `Ask a question` · `Stop messages`

**en**
> Hello {{1}}, thank you for your enquiry with {{2}} for {{3}} admission. I'm the school's admission assistant. I can share details about the school or book a campus visit for you. How can I help?

**hi**
> नमस्ते {{1}}, {{2}} में {{3}} एडमिशन के लिए पूछताछ करने के लिए धन्यवाद। मैं स्कूल का एडमिशन असिस्टेंट हूँ। मैं आपको स्कूल की जानकारी दे सकता हूँ या कैंपस विज़िट बुक कर सकता हूँ। बताइए, मैं कैसे मदद करूँ?

Buttons (hi): `कैंपस विज़िट बुक करें` · `सवाल पूछें` · `मैसेज बंद करें`

Sample: `Priya` · `Sunrise Demo Public School` · `Nursery`

---

## 2. `visit_confirmation`: campus visit booked
- Category: **UTILITY**. Recipient: parent.
- Variables: `{{1}}` parent name, `{{2}}` school name, `{{3}}` date (e.g. "Sat, 7 Nov"), `{{4}}` time (e.g. "10:00 AM"), `{{5}}` address.
- Buttons: `Reschedule` · `Cancel visit` · `Stop messages`

**en**
> Hi {{1}}, your campus visit at {{2}} is confirmed for {{3}} at {{4}}. Address: {{5}}. Please reply here if you need to change the time.

**hi**
> नमस्ते {{1}}, {{2}} में आपकी कैंपस विज़िट {{3}} को {{4}} बजे के लिए कन्फ़र्म है। पता: {{5}}। समय बदलना हो तो यहीं जवाब दें।

Buttons (hi): `समय बदलें` · `विज़िट रद्द करें` · `मैसेज बंद करें`

---

## 3. `visit_reminder_day_before`: day-before reminder
- Category: **UTILITY**. Recipient: parent. Sent at 18:00 IST the day before.
- Variables: `{{1}}` parent name, `{{2}}` school name, `{{3}}` time.
- Buttons: `I'll be there` · `Reschedule` · `Stop messages`

**en**
> Hi {{1}}, a reminder that your campus visit at {{2}} is tomorrow at {{3}}. We look forward to meeting you.

**hi**
> नमस्ते {{1}}, याद दिला दें कि {{2}} में आपकी कैंपस विज़िट कल {{3}} बजे है। हमें आपसे मिलने का इंतज़ार रहेगा।

Buttons (hi): `मैं आऊँगा/आऊँगी` · `समय बदलें` · `मैसेज बंद करें`

---

## 4. `visit_reminder_morning`: morning-of reminder
- Category: **UTILITY**. Recipient: parent. Sent at 08:00 IST on the day (or 2 hours before, whichever is later).
- Variables: `{{1}}` parent name, `{{2}}` time, `{{3}}` school name, `{{4}}` maps link or address.
- Buttons: `On my way` · `Reschedule` · `Stop messages`

**en**
> Good morning {{1}}! See you today at {{2}} at {{3}}. Directions: {{4}}

**hi**
> सुप्रभात {{1}}! आज {{2}} बजे {{3}} में मिलते हैं। रास्ता: {{4}}

Buttons (hi): `रास्ते में हूँ` · `समय बदलें` · `मैसेज बंद करें`

---

## 5. `counselor_lead_alert`: hot-lead / escalation alert to counselor
- Category: **UTILITY**. Recipient: school counselor (staff number). English only (staff); a Hindi version is optional.
- Variables: `{{1}}` lead reference (e.g. "#1042"), `{{2}}` parent name, `{{3}}` grade, `{{4}}` reason (e.g. "Asked about Class 10 results – not in KB"), `{{5}}` last message excerpt.
- Buttons (quick reply, payload carries the lead id): `Visit booked` · `Visited` · `Admitted` · `Not interested`
  - Meta allows up to 10 quick replies; WhatsApp shows the first 3 inline and the rest under "See all options". TO VERIFY.
- Phone numbers are not put in the template. The counselor opens the lead from the dashboard link (added later as a URL button).

**en**
> New lead needs attention: {{1}} – {{2}}, {{3}}. Reason: {{4}}. Last message: "{{5}}". Tap a button to update the status.

**hi**
> नई लीड पर ध्यान दें: {{1}} – {{2}}, {{3}}। कारण: {{4}}। आख़िरी मैसेज: "{{5}}"। स्टेटस अपडेट करने के लिए बटन दबाएँ।

---

## 6. `weekly_report_ready`: weekly report notice
- Category: **UTILITY**. Recipient: school approver / principal. Monday 09:00 IST.
- Variables: `{{1}}` name, `{{2}}` week label (e.g. "26 Oct – 1 Nov"), `{{3}}` visits booked, `{{4}}` cost per visit (e.g. "₹1,850").
- Buttons: URL button `View report` → `https://<dashboard>/reports/{{1}}` (dynamic suffix).

**en**
> Hello {{1}}, your admissions report for {{2}} is ready. Campus visits booked: {{3}}. Cost per visit: {{4}}. Tap below to read the full report.

**hi**
> नमस्ते {{1}}, {{2}} की आपकी एडमिशन रिपोर्ट तैयार है। बुक हुई कैंपस विज़िट: {{3}}। प्रति विज़िट लागत: {{4}}। पूरी रिपोर्ट पढ़ने के लिए नीचे टैप करें।

---

## 7. `creative_approval_request`: new ad creative needs approval
- Category: **UTILITY**. Recipient: school approver.
- Header: image (the rendered creative).
- Variables: `{{1}}` name, `{{2}}` creative label (e.g. "Nursery · Safety · Hindi"), `{{3}}` headline.
- Buttons (quick reply, payload carries the creative id): `Approve` · `Reject` · `See in dashboard`

**en**
> Hello {{1}}, a new ad is ready for your approval: {{2}}. Headline: "{{3}}". Nothing goes live without your approval.

**hi**
> नमस्ते {{1}}, एक नया विज्ञापन आपकी मंज़ूरी के लिए तैयार है: {{2}}। हेडलाइन: "{{3}}"। आपकी मंज़ूरी के बिना कुछ भी लाइव नहीं होगा।

Buttons (hi): `मंज़ूर करें` · `अस्वीकार करें` · `डैशबोर्ड में देखें`

---

## Notes for submission
- Submit both languages under the same template name.
- After approval, record each template's name, language and status in config. Code checks this before sending anything outside the 24-hour window.
- A Hinglish template is not a separate Meta language. Hinglish parents get `en` templates, and free-form replies match their style inside the window.
