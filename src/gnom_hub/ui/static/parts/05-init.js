/* part: 05-init.js  lines 4268-4656 of app.js — edit parts, run scripts/build_ui_js.py */
  async function refreshBusyFromServer() {
    try {
      const b = await api("GET", "/api/jobs/busy");
      if (b && b.busy) {
        if (typeof showBusyBanner === "function") {
          showBusyBanner({
            busy_job_id: b.busy_job_id,
            busy_name: b.busy_name,
            busy_stage: b.busy_stage,
            cancel: b.cancel,
          });
        }
        if (typeof setChatBusy === "function" && !chatBusy) {
          // do not lock chat fully — only banner; user can cancel
        }
      } else if (typeof hideBusyBanner === "function") {
        hideBusyBanner();
      }
    } catch (_e) {
      /* ignore */
    }
  }

  function init() {
    if (typeof buildAgentLayers === "function") buildAgentLayers();
    if (typeof buildChatLayers === "function") buildChatLayers();
    renderCards();
    bindTooltipHovers();
    bindTuneSliders();
    refreshBusyFromServer();

    els.btnSend.addEventListener("click", sendChat);
    if (els.btnExecute) els.btnExecute.addEventListener("click", runExecute);
    const btnSendExec = document.getElementById("btn-send-exec");
    if (btnSendExec) btnSendExec.addEventListener("click", sendAndExecute);
    const btnCancel = document.getElementById("btn-cancel");
    if (btnCancel) btnCancel.addEventListener("click", cancelCurrentJob);
    const btnCancelBusy = document.getElementById("btn-cancel-busy");
    if (btnCancelBusy) btnCancelBusy.addEventListener("click", cancelCurrentJob);
    if (els.btnMic) els.btnMic.addEventListener("click", toggleMic);
    const presetApply = document.getElementById("sys-preset-apply");
    const presetDel = document.getElementById("sys-preset-delete");
    if (presetApply) presetApply.addEventListener("click", applySelectedPreset);
    if (presetDel) presetDel.addEventListener("click", deleteSelectedPreset);
    const teamApply = document.getElementById("sys-team-apply");
    const teamSave = document.getElementById("sys-team-save");
    const teamDel = document.getElementById("sys-team-delete");
    const planMode = document.getElementById("sys-plan-mode");
    if (teamApply) teamApply.addEventListener("click", applySelectedTeam);
    if (teamSave) teamSave.addEventListener("click", saveCurrentTeam);
    if (teamDel) teamDel.addEventListener("click", deleteSelectedTeam);
    if (planMode) planMode.addEventListener("change", setPlanModeFromUi);
    loadChatHist();
    els.chatInput.addEventListener("keydown", function (ev) {
      // Terminal-style history: ↑ older · ↓ newer
      if (ev.key === "ArrowUp") {
        ev.preventDefault();
        chatHistNav(-1);
        return;
      }
      if (ev.key === "ArrowDown") {
        ev.preventDefault();
        chatHistNav(1);
        return;
      }
      // Typing resets history cursor to "live draft"
      if (ev.key.length === 1 || ev.key === "Backspace" || ev.key === "Delete") {
        if (chatHistIdx !== -1) {
          chatHistIdx = -1;
          chatDraft = "";
        }
      }
      // Ctrl/Cmd+Enter = Execute; plain Enter = Send
      if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) {
        ev.preventDefault();
        runExecute();
        return;
      }
      if (ev.key === "Enter") {
        ev.preventDefault();
        sendChat();
      }
    });
    document.addEventListener("keydown", function (ev) {
      // Esc: close overlays first, else cancel running job
      if (ev.key === "Escape") {
        if (els.toolsModal && !els.toolsModal.hidden) {
          ev.preventDefault();
          closeToolsModal();
          return;
        }
        if (els.usageModal && !els.usageModal.hidden) {
          ev.preventDefault();
          closeUsageModal();
          return;
        }
        if (els.vectorModal && !els.vectorModal.hidden) {
          ev.preventDefault();
          closeVectorModal();
          return;
        }
        if (document.getElementById("diff-overlay")) {
          ev.preventDefault();
          closeDiffOverlay();
          return;
        }
        if (document.getElementById("worker-fs-overlay")) {
          ev.preventDefault();
          closeWorkerFullscreen();
          return;
        }
        if (chatBusy) {
          ev.preventDefault();
          cancelCurrentJob();
        }
        return;
      }
      // Ctrl/Cmd+S = save HOT + agents (skip when typing in modal fields is fine — still save)
      if ((ev.ctrlKey || ev.metaKey) && (ev.key === "s" || ev.key === "S")) {
        ev.preventDefault();
        onSave();
      }
    });
    const btnCopyAll = document.getElementById("btn-copy-all");
    if (btnCopyAll) btnCopyAll.addEventListener("click", copyAllWorkerResults);
    const btnDiff = document.getElementById("btn-diff");
    if (btnDiff) btnDiff.addEventListener("click", openWorkerDiff);
    const hist = document.getElementById("result-history");
    if (hist) {
      hist.addEventListener("change", function () {
        if (hist.value) restoreHistoryEntry(hist.value);
      });
    }
    loadResultHistory();    renderHistorySelect();

    const btnReexec = document.getElementById("btn-reexec");
    if (btnReexec) btnReexec.addEventListener("click", reexecFromHistory);
    const btnHistExport = document.getElementById("btn-hist-export");
    if (btnHistExport) btnHistExport.addEventListener("click", exportResultHistory);
    const histSel = document.getElementById("result-history");
    if (histSel) {
      histSel.addEventListener("change", function () {
        const re = document.getElementById("btn-reexec");
        if (!re) return;
        const entry = resultHistory.find(function (e) {
          return e.id === histSel.value;
        });
        re.disabled = !(entry && (entry.can_reexec || entry.user_text || entry.brainstorm_notes));
        re.dataset.historyId = entry ? entry.id : "";
      });
    }
    const packExp = document.getElementById("sys-pack-export");
    if (packExp) packExp.addEventListener("click", exportSessionPack);
    const packImp = document.getElementById("sys-pack-import");
    if (packImp) packImp.addEventListener("click", importSessionPack);
    const packFilter = document.getElementById("sys-pack-filter");
    if (packFilter) {
      packFilter.addEventListener("input", function () {
        renderPackList(packListCache);
      });
    }
    const hotAdd = document.getElementById("sys-hot-add");
    if (hotAdd) hotAdd.addEventListener("click", addHotFact);
    const hotClear = document.getElementById("sys-hot-clear");
    if (hotClear) hotClear.addEventListener("click", clearHotFacts);
    const hotInput = document.getElementById("sys-hot-input");
    if (hotInput) {
      hotInput.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter") {
          ev.preventDefault();
          addHotFact();
        }
      });
    }
    const warmAdd = document.getElementById("sys-warm-add");
    if (warmAdd) warmAdd.addEventListener("click", addWarmFact);
    const warmClear = document.getElementById("sys-warm-clear");
    if (warmClear) warmClear.addEventListener("click", clearWarmFacts);
    const warmInput = document.getElementById("sys-warm-input");
    if (warmInput) {
      warmInput.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter") {
          ev.preventDefault();
          addWarmFact();
        }
      });
    }
    const packFile = document.getElementById("sys-pack-file");
    if (packFile) packFile.addEventListener("change", onSessionPackFile);

    updateBox3Toolbar();
    if (typeof bindBoxLayerControls === "function") bindBoxLayerControls();
    const btnClearChat = document.getElementById("btn-clear-chat");
    if (btnClearChat) btnClearChat.addEventListener("click", clearChatLog);
    els.btnSave.addEventListener("click", onSave);
    if (els.btnHelp) els.btnHelp.addEventListener("click", onHelp);
    if (els.btnSystem) els.btnSystem.addEventListener("click", openSystemModal);
    if (els.btnWorkspace) els.btnWorkspace.addEventListener("click", openWorkspaceModal);
    if (els.btnTools) els.btnTools.addEventListener("click", openToolsModal);
    const histCopy = document.getElementById("tools-hist-copy");
    if (histCopy) histCopy.addEventListener("click", copyToolsHistory);
    const histRef = document.getElementById("tools-hist-refresh");
    if (histRef)
      histRef.addEventListener("click", function () {
        const calls =
          lastSnapshot && lastSnapshot.pipeline && lastSnapshot.pipeline.tool_calls
            ? lastSnapshot.pipeline.tool_calls
            : lastToolCalls || [];
        renderToolsRunHistory(calls);
        if (typeof toast === "function") toast("Tool history refreshed", "info");
      });

    if (els.toolsBadge) {
      els.toolsBadge.addEventListener("click", openToolsModal);
      els.toolsBadge.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          openToolsModal();
        }
      });
    }
    const cuInspectBtn = document.getElementById("cu-inspect");
    const cuClickBtn = document.getElementById("cu-click");
    const cuTypeBtn = document.getElementById("cu-type-btn");
    const cuShellBtn = document.getElementById("cu-shell-btn");
    if (cuInspectBtn) cuInspectBtn.addEventListener("click", cuInspect);
    if (cuClickBtn) cuClickBtn.addEventListener("click", cuClick);
    if (cuTypeBtn) cuTypeBtn.addEventListener("click", cuType);
    if (cuShellBtn) cuShellBtn.addEventListener("click", cuShell);
    const toolsClose = document.getElementById("tools-close");
    if (toolsClose) toolsClose.addEventListener("click", closeToolsModal);
    if (els.toolsModal) {
      els.toolsModal.addEventListener("click", function (ev) {
        if (ev.target === els.toolsModal) closeToolsModal();
      });
    }
    const toolsRun = document.getElementById("tools-run");
    if (toolsRun) toolsRun.addEventListener("click", runSelectedTool);
    const toolsRefresh = document.getElementById("tools-refresh");
    if (toolsRefresh) {
      toolsRefresh.addEventListener("click", function () {
        refreshToolsModal({ reload: true });
      });
    }
    const toolsFetchBtn = document.getElementById("tools-fetch-btn");
    if (toolsFetchBtn) toolsFetchBtn.addEventListener("click", runQuickFetch);
    const toolsArgs = document.getElementById("tools-args");
    if (toolsArgs) {
      toolsArgs.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter") {
          ev.preventDefault();
          runSelectedTool();
        }
      });
    }
    const toolsFetchUrl = document.getElementById("tools-fetch-url");
    if (toolsFetchUrl) {
      toolsFetchUrl.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter") {
          ev.preventDefault();
          runQuickFetch();
        }
      });
    }
    if (els.flexSelect) els.flexSelect.addEventListener("change", onFlexSelectChange);
    const ckSave = document.getElementById("sys-ckpt-save");
    const ckLoad = document.getElementById("sys-ckpt-load");
    if (ckSave) ckSave.addEventListener("click", saveCheckpoint);
    if (ckLoad) ckLoad.addEventListener("click", loadCheckpoint);
    const sysBackup = document.getElementById("sys-backup");
    const sysClean = document.getElementById("sys-clean");
    if (sysBackup) sysBackup.addEventListener("click", runBackup);
    if (sysClean) sysClean.addEventListener("click", runCleanState);
    const tunePreset = document.getElementById("tune-preset-save");
    if (tunePreset) tunePreset.addEventListener("click", saveWorkerPresetFromTune);
    if (els.btnReset) els.btnReset.addEventListener("click", onReset);
    const wsClose = document.getElementById("workspace-close");
    const wsClear = document.getElementById("ws-clear-temp");
    if (wsClose) wsClose.addEventListener("click", closeWorkspaceModal);
    if (wsClear) wsClear.addEventListener("click", clearTempWs);
    const wsDlTemp = document.getElementById("ws-dl-temp");
    if (wsDlTemp) {
      wsDlTemp.addEventListener("click", function () {
        downloadWorkspaceZip("temp");
      });
    }
    const wsDlPerm = document.getElementById("ws-dl-perm");
    if (wsDlPerm) {
      wsDlPerm.addEventListener("click", function () {
        downloadWorkspaceZip("perm");
      });
    }
    const wsDlAll = document.getElementById("ws-dl-all");
    if (wsDlAll) {
      wsDlAll.addEventListener("click", function () {
        downloadWorkspaceZip("all");
      });
    }
    if (els.workspaceModal) {
      els.workspaceModal.addEventListener("click", function (ev) {
        if (ev.target === els.workspaceModal) closeWorkspaceModal();
      });
    }
    if (els.btnArchive) els.btnArchive.addEventListener("click", onArchive);
    const tuneClose = document.getElementById("tune-close");
    const tuneSave = document.getElementById("tune-save");
    if (tuneClose) tuneClose.addEventListener("click", closeTuneModal);
    if (tuneSave) tuneSave.addEventListener("click", saveTuneModal);
    if (els.tuneModal) {
      els.tuneModal.addEventListener("click", function (ev) {
        if (ev.target === els.tuneModal) closeTuneModal();
      });
    }
    const sysClose = document.getElementById("system-close");
    const sysSave = document.getElementById("system-save");
    if (sysClose) sysClose.addEventListener("click", closeSystemModal);
    if (sysSave) sysSave.addEventListener("click", saveSystemModal);
    if (els.systemModal) {
      els.systemModal.addEventListener("click", function (ev) {
        if (ev.target === els.systemModal) closeSystemModal();
      });
    }
    if (els.godBadge) {
      els.godBadge.addEventListener("click", toggleGodMode);
      els.godBadge.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          toggleGodMode();
        }
      });
    }
    if (els.coldBadge) {
      els.coldBadge.addEventListener("click", openColdBrowser);
      els.coldBadge.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          openColdBrowser();
        }
      });
    }
    if (els.docsBadge) {
      els.docsBadge.addEventListener("click", openDocsModal);
      els.docsBadge.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          openDocsModal();
        }
      });
    }
    if (els.skillsBadge) {
      els.skillsBadge.addEventListener("click", openSkillsModal);
      els.skillsBadge.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          openSkillsModal();
        }
      });
    }
    if (els.vecBadge) {
      els.vecBadge.addEventListener("click", openVectorModal);
      els.vecBadge.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          openVectorModal();
        }
      });
    }
    if (els.costBadge) {
      els.costBadge.addEventListener("click", openUsageModal);
      els.costBadge.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          openUsageModal();
        }
      });
    }
    const usageClose = document.getElementById("usage-close");
    if (usageClose) usageClose.addEventListener("click", closeUsageModal);
    if (els.usageModal) {
      els.usageModal.addEventListener("click", function (ev) {
        if (ev.target === els.usageModal) closeUsageModal();
      });
    }
    const usageRefresh = document.getElementById("usage-refresh");
    if (usageRefresh) usageRefresh.addEventListener("click", refreshUsageModal);
    const usageReset = document.getElementById("usage-reset");
    if (usageReset) usageReset.addEventListener("click", resetUsageCounters);
    const vectorClose = document.getElementById("vector-close");
    if (vectorClose) vectorClose.addEventListener("click", closeVectorModal);
    if (els.vectorModal) {
      els.vectorModal.addEventListener("click", function (ev) {
        if (ev.target === els.vectorModal) closeVectorModal();
      });
    }
    const vectorSearchBtn = document.getElementById("vector-search-btn");
    if (vectorSearchBtn) vectorSearchBtn.addEventListener("click", searchVectors);
    const vectorRefresh = document.getElementById("vector-refresh");
    if (vectorRefresh) vectorRefresh.addEventListener("click", refreshVectorList);
    const vectorClear = document.getElementById("vector-clear");
    if (vectorClear) vectorClear.addEventListener("click", clearVectorStore);
    const vectorAddBtn = document.getElementById("vector-add-btn");
    if (vectorAddBtn) vectorAddBtn.addEventListener("click", addVectorDoc);
    const vectorEmbedApply = document.getElementById("vector-embedder-apply");
    if (vectorEmbedApply) vectorEmbedApply.addEventListener("click", applyVectorEmbedder);
    const vectorEmbedInstall = document.getElementById("vector-embedder-install");
    if (vectorEmbedInstall) vectorEmbedInstall.addEventListener("click", installNeuralEmbedder);
    const skillsClose = document.getElementById("skills-close");
    if (skillsClose) skillsClose.addEventListener("click", closeSkillsModal);
    if (els.skillsModal) {
      els.skillsModal.addEventListener("click", function (ev) {
        if (ev.target === els.skillsModal) closeSkillsModal();
      });
    }
    const skillsReload = document.getElementById("skills-reload");
    if (skillsReload) skillsReload.addEventListener("click", reloadSkills);
    const skillsInstallBtn = document.getElementById("skills-install-btn");
    if (skillsInstallBtn) skillsInstallBtn.addEventListener("click", installSkillPath);
    const skillsLearnLast = document.getElementById("skills-learn-last");
    if (skillsLearnLast) skillsLearnLast.addEventListener("click", learnSkillFromLast);
    const docsClose = document.getElementById("docs-close");
    if (docsClose) docsClose.addEventListener("click", closeDocsModal);
    if (els.docsModal) {
      els.docsModal.addEventListener("click", function (ev) {
        if (ev.target === els.docsModal) closeDocsModal();
      });
    }
    const docsSearchBtn = document.getElementById("docs-search-btn");
    if (docsSearchBtn) docsSearchBtn.addEventListener("click", runDocsSearch);
    const docsQuery = document.getElementById("docs-query");
    if (docsQuery) {
      docsQuery.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter") {
          ev.preventDefault();
          runDocsSearch();
        }
      });
    }
    const vectorQuery = document.getElementById("vector-query");
    if (vectorQuery) {
      vectorQuery.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter") {
          ev.preventDefault();
          searchVectors();
        }
      });
    }
    const vectorAddInput = document.getElementById("vector-add-input");
    if (vectorAddInput) {
      vectorAddInput.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter") {
          ev.preventDefault();
          addVectorDoc();
        }
      });
    }
    if (els.btnColdClose) {
      els.btnColdClose.addEventListener("click", function () {
        hideColdBrowser();
        showTooltip("box1");
      });
    }
    const btnColdRestore = document.getElementById("btn-cold-restore");
    if (btnColdRestore) {
      btnColdRestore.addEventListener("click", restoreSelectedCold);
    }
    const btnColdDelete = document.getElementById("btn-cold-delete");
    if (btnColdDelete) {
      btnColdDelete.addEventListener("click", deleteSelectedCold);
    }

    document.querySelectorAll(".btn-clarify").forEach(function (btn) {
      btn.addEventListener("click", function () {
        onClarify(btn.getAttribute("data-answer"));
      });
    });

    showTooltip("box1");
    bootstrap();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();


  function initMobileBoxTabs() {
    const bar = document.getElementById("mobile-box-tabs");
    if (!bar) return;
    function apply() {
      const narrow = window.matchMedia("(max-width: 640px)").matches;
      bar.hidden = !narrow;
      document.body.classList.toggle("mobile-box-mode", narrow);
      if (narrow && !document.body.className.match(/show-box-/)) {
        document.body.classList.add("show-box-1");
      }
      if (!narrow) {
        document.body.classList.remove("show-box-1", "show-box-2", "show-box-3");
      }
    }
    bar.querySelectorAll("[data-box-tab]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const n = btn.getAttribute("data-box-tab") || "1";
        document.body.classList.remove("show-box-1", "show-box-2", "show-box-3");
        document.body.classList.add("show-box-" + n);
        bar.querySelectorAll(".mobile-box-tab").forEach(function (b) {
          b.classList.toggle("is-active", b === btn);
        });
      });
    });
    window.addEventListener("resize", apply);
    apply();
  }
  initMobileBoxTabs();
