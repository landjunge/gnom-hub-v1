(() => {
  "use strict";

  // V4 Tool/Brand module.
  // Logos are intentionally swappable assets. Drafts live in Notion; approved
  // SVGs can later replace these paths without changing launcher behavior.
  window.GNOM_TOOL_MANIFEST = [
    {
      key: "1",
      id: "netzwerkpunkt",
      name: "NetzwerkPunkt",
      role: "Dachmarke",
      logo: "",
      fallback: "NP",
    },
    {
      key: "2",
      id: "gnom-hub",
      name: "Gnom-Hub-V1",
      role: "Agenten-Hub",
      logo: "",
      fallback: "GH",
      home: true,
    },
    {
      key: "3",
      id: "threaddesk",
      name: "ThreadDesk",
      role: "Arbeitsgedächtnis",
      logo: "",
      fallback: "TD",
    },
    {
      key: "4",
      id: "tollgate",
      name: "TollGate",
      role: "Kosten & Freigaben",
      logo: "",
      fallback: "TG",
    },
    {
      key: "5",
      id: "4allpass",
      name: "4AllPass",
      role: "Zugangsdaten",
      logo: "",
      fallback: "4A",
    },
  ];
})();
