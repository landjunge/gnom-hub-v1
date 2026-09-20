/* part: 02-speech.js — edit parts, run scripts/build_ui_js.py */
  /** Recent spoken fingerprints — never queue the same text twice. */
  const ttsSpokenFp = {};
  let ttsToastAt = 0;
  let ttsPrepareInflight = {};

  function stripForSpeech(text) {
    let s = String(text || "");
    s = s.replace(/```[\s\S]*?```/g, " ");
    s = s.replace(/<!DOCTYPE[\s\S]*$/i, " ");
    s = s.replace(/<[^>]+>/g, " ");
    s = s.replace(/&[a-z]+;/gi, " ");
    s = s.replace(/\s+/g, " ").trim();
    // Keep spoken Gedanken short (product: not a lecture)
    return s.slice(0, 520);
  }

  function speechFp(text) {
    return String(text || "")
      .toLowerCase()
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, 220);
  }

  function looksMostlyGermanClient(text) {
    const t = String(text || "").trim();
    if (!t) return true;
    if (/[äöüÄÖÜß]/.test(t)) return true;
    if (/\b(der|die|das|und|ich|nicht|eine|für|mit|soll|wird|auch|noch|nur|wenn|dann|bitte|hier|box)\b/i.test(t)) {
      return true;
    }
    const en = (t.match(/\b(the|and|with|for|this|that|should|would|could|build|page|user|about|from|have|will)\b/gi) || []).length;
    return en < 3;
  }

  function looksMostlyEnglishClient(text) {
    const t = String(text || "").trim();
    if (!t) return false;
    if (/[äöüÄÖÜß]/.test(t)) return false;
    if (/\b(der|die|das|und|ich|nicht|eine|für|mit|soll)\b/i.test(t)) return false;
    const en = (t.match(/\b(the|and|with|for|this|that|should|would|could|build|page|user|about|from|have|will)\b/gi) || []).length;
    return en >= 3;
  }

  function germanizeThoughtForSpeech(text, label) {
    const clean = stripForSpeech(text);
    if (!clean) return "";
    if (uiLang === "en") return clean;
    if (looksMostlyEnglishClient(clean) || !looksMostlyGermanClient(clean)) {
      const who = label || "Agent";
      return who + ". Kurzer Gedanke: ich priorisiere die User-Anfrage und bleibe knapp. Details stehen in Box 2 und Box 3.";
    }
    return clean;
  }

  function maybeSpeakFlexSupport(p, snap) {
    const a = typeof findAgent === "function" ? findAgent("flex") : null;
    if (!a || !a.tts) return;
    p = p || {};
    const thoughts = (snap && snap.agent_thoughts) || lastAgentThoughts || {};
    const notes = stripForSpeech(p.flex_notes || "");
    const thought = stripForSpeech(thoughts.flex || "");
    let body = notes || thought;
    if (!body) return;
    body = body.replace(/^#+\s*/gm, "").replace(/\*\*/g, "").replace(/`+/g, "").replace(/\s+/g, " ").trim().slice(0, 500);
    if (!body) return;
    let spoken = "Flex, nur für dich. " + body;
    if (p.stage === "done" && p.deliverable_ok === true) {
      spoken += " Wenn du magst: sag mir kurz, ob das Ergebnis für dich passt.";
    }
    speakOrQueue(spoken, "flex");
  }
