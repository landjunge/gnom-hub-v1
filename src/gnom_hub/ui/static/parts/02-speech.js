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
    return s.slice(0, 520);
  }

  function speechFp(text) {
    return String(text || "").toLowerCase().replace(/\s+/g, " ").trim().slice(0, 220);
  }
