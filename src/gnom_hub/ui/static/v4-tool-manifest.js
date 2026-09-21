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
      url: "https://netzwerkpunkt.de/",
      logo: "/static/brand/netzwerkpunkt/logo.svg",
      fallback: "NP",
    },
    {
      key: "2",
      id: "gnom-hub",
      name: "Gnom-Hub-V1",
      role: "Agenten-Hub",
      url: null,
      logo: "/static/brand/gnom-hub/logo.svg",
      fallback: "GH",
      home: true,
    },
    {
      key: "3",
      id: "threaddesk",
      name: "ThreadDesk",
      role: "Arbeitsgedächtnis",
      url: "https://threaddesk.netzwerkpunkt.de/",
      logo: "/static/brand/threaddesk/logo.svg",
      fallback: "TD",
    },
    {
      key: "4",
      id: "tollgate",
      name: "TollGate",
      role: "Kosten & Freigaben",
      url: "https://tollgate.netzwerkpunkt.de/",
      logo: "/static/brand/tollgate/logo.svg",
      fallback: "TG",
    },
    {
      key: "5",
      id: "4allpass",
      name: "4AllPass",
      role: "Zugangsdaten",
      url: "https://4allpass.netzwerkpunkt.de/",
      logo: "/static/brand/4allpass/logo.svg",
      fallback: "4A",
    },
  ];
})();
