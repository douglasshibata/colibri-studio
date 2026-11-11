// Colibri Studio Workstation Frontend Script

document.addEventListener("DOMContentLoaded", () => {
  // Navigation Tabs
  const navItems = document.querySelectorAll(".nav-item");
  const tabPanes = document.querySelectorAll(".tab-pane");

  navItems.forEach(item => {
    item.addEventListener("click", () => {
      const tabName = item.getAttribute("data-tab");
      navItems.forEach(n => n.classList.remove("active"));
      tabPanes.forEach(p => p.classList.remove("active"));

      item.classList.add("active");
      document.getElementById(`tab-${tabName}`).classList.add("active");

      if (tabName === "hardware") fetchHardwareMetrics();
      if (tabName === "models") fetchModels();
      if (tabName === "brain") renderBrainCanvas();
      if (tabName === "settings") loadSettings();
    });
  });

  // State
  let currentConvId = null;
  let activeMessages = [];
  let currentSystemPrompt = "";
  let isGenerating = false;
  let currentAbortController = null;

  // Initial Load
  fetchConversations();
  fetchModels();
  setInterval(fetchHardwareMetrics, 3000);

  // Conversation Management
  async function fetchConversations() {
    try {
      const res = await fetch("/api/v1/conversations");
      const convs = await res.json();
      const listEl = document.getElementById("conv-list");
      listEl.innerHTML = "";

      convs.forEach(c => {
        const item = document.createElement("div");
        item.className = `conv-item ${c.id === currentConvId ? 'active' : ''}`;
        item.innerText = c.title || "Untitled Chat";
        item.onclick = () => loadConversation(c.id);
        listEl.appendChild(item);
      });
    } catch (e) {
      console.error("Failed to load conversations", e);
    }
  }

  document.getElementById("new-conv-btn").onclick = async () => {
    try {
      const res = await fetch("/api/v1/conversations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: "New Conversation" })
      });
      const conv = await res.json();
      currentConvId = conv.id;
      fetchConversations();
      loadConversation(conv.id);
    } catch (e) {
      console.error(e);
    }
  };

  async function loadConversation(id) {
    currentConvId = id;
    fetchConversations();
    try {
      const res = await fetch(`/api/v1/conversations/${id}`);
      const conv = await res.json();
      document.getElementById("chat-title").innerText = conv.title;
      currentSystemPrompt = conv.system_prompt || "";
      document.getElementById("system-prompt-input").value = currentSystemPrompt;
      activeMessages = conv.messages || [];
      renderMessages(activeMessages);
    } catch (e) {
      console.error(e);
    }
  }

  // System Prompt & Rename Controls
  document.getElementById("sys-prompt-btn").onclick = () => {
    const bar = document.getElementById("system-prompt-bar");
    bar.style.display = bar.style.display === "none" ? "flex" : "none";
  };

  document.getElementById("save-sys-prompt-btn").onclick = async () => {
    if (!currentConvId) return;
    const promptVal = document.getElementById("system-prompt-input").value.trim();
    currentSystemPrompt = promptVal;
    await fetch(`/api/v1/conversations/${currentConvId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ system_prompt: promptVal })
    });
    document.getElementById("system-prompt-bar").style.display = "none";
  };

  document.getElementById("rename-conv-btn").onclick = async () => {
    if (!currentConvId) return;
    const newTitle = prompt("Enter conversation title:", document.getElementById("chat-title").innerText);
    if (newTitle) {
      document.getElementById("chat-title").innerText = newTitle;
      await fetch(`/api/v1/conversations/${currentConvId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: newTitle })
      });
      fetchConversations();
    }
  };

  document.getElementById("delete-conv-btn").onclick = async () => {
    if (!currentConvId) return;
    if (confirm("Delete this conversation?")) {
      await fetch(`/api/v1/conversations/${currentConvId}`, { method: "DELETE" });
      currentConvId = null;
      activeMessages = [];
      fetchConversations();
      renderMessages([]);
      document.getElementById("chat-title").innerText = "New Conversation";
    }
  };

  function renderMessages(messages) {
    const chatContainer = document.getElementById("chat-messages");
    chatContainer.innerHTML = "";

    if (messages.length === 0) {
      chatContainer.innerHTML = `
        <div class="welcome-box">
          <h2>Welcome to Colibri Studio</h2>
          <p>Run 744B+ parameter MoE models locally with expert multitiering.</p>
        </div>`;
      return;
    }

    messages.forEach(m => {
      appendMessageUI(m.role, m.content);
    });
  }

  function appendMessageUI(role, content) {
    const chatContainer = document.getElementById("chat-messages");
    const row = document.createElement("div");
    row.className = `msg-row ${role}`;

    const bubble = document.createElement("div");
    bubble.className = "msg-bubble";

    if (typeof marked !== "undefined") {
      bubble.innerHTML = marked.parse(content);
    } else {
      bubble.innerText = content;
    }

    // Add Copy Button
    const copyBtn = document.createElement("button");
    copyBtn.className = "btn btn-secondary btn-sm copy-btn";
    copyBtn.innerText = "Copy";
    copyBtn.onclick = () => {
      navigator.clipboard.writeText(content);
      copyBtn.innerText = "Copied!";
      setTimeout(() => copyBtn.innerText = "Copy", 2000);
    };
    bubble.appendChild(copyBtn);

    row.appendChild(bubble);
    chatContainer.appendChild(row);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    return bubble;
  }

  // Stop Generation
  document.getElementById("stop-btn").onclick = () => {
    if (currentAbortController) {
      currentAbortController.abort();
      isGenerating = false;
      toggleGeneratingState(false);
    }
  };

  function toggleGeneratingState(generating) {
    isGenerating = generating;
    document.getElementById("send-btn").style.display = generating ? "none" : "inline-block";
    document.getElementById("stop-btn").style.display = generating ? "inline-block" : "none";
  }

  // Send Prompt & Streaming
  document.getElementById("send-btn").onclick = sendPrompt;
  document.getElementById("chat-input").onkeydown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendPrompt();
    }
  };

  document.getElementById("regenerate-btn").onclick = () => {
    if (activeMessages.length >= 2 && !isGenerating) {
      // Find last user prompt
      const lastUserMsg = activeMessages.filter(m => m.role === "user").pop();
      if (lastUserMsg) {
        document.getElementById("chat-input").value = lastUserMsg.content;
        sendPrompt();
      }
    }
  };

  async function sendPrompt() {
    const inputEl = document.getElementById("chat-input");
    const text = inputEl.value.trim();
    if (!text || isGenerating) return;

    if (!currentConvId) {
      const res = await fetch("/api/v1/conversations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: text.substring(0, 20) })
      });
      const conv = await res.json();
      currentConvId = conv.id;
      fetchConversations();
    }

    // Persist User Message to DB
    await fetch(`/api/v1/conversations/${currentConvId}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role: "user", content: text })
    });
    activeMessages.push({ role: "user", content: text });

    appendMessageUI("user", text);
    inputEl.value = "";

    const assistantBubble = appendMessageUI("assistant", "...");
    toggleGeneratingState(true);
    currentAbortController = new AbortController();

    const startTime = Date.now();
    let firstTokenTime = null;
    let totalTokens = 0;

    // Build payload messages with optional system prompt
    const payloadMessages = [];
    if (currentSystemPrompt) {
      payloadMessages.push({ role: "system", content: currentSystemPrompt });
    }
    payloadMessages.push(...activeMessages);

    try {
      const response = await fetch("/v1/chat/completions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: currentAbortController.signal,
        body: JSON.stringify({
          messages: payloadMessages,
          temperature: parseFloat(document.getElementById("temp-input").value),
          top_p: parseFloat(document.getElementById("topp-input").value),
          max_tokens: parseInt(document.getElementById("maxtok-input").value),
          stream: true
        })
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let fullText = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split("\n");
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const dataStr = line.slice(6).trim();
            if (dataStr === "[DONE]") break;
            try {
              const data = JSON.parse(dataStr);
              const delta = data.choices[0]?.delta?.content || "";
              if (delta) {
                if (!firstTokenTime) firstTokenTime = Date.now();
                fullText += delta;
                totalTokens++;
                assistantBubble.innerHTML = marked.parse(fullText);

                // Update Telemetry
                const elapsedSec = (Date.now() - startTime) / 1000;
                const ttft = firstTokenTime ? ((firstTokenTime - startTime) / 1000).toFixed(2) : "0.0";
                const tokSec = (totalTokens / max(elapsedSec, 0.001)).toFixed(1);

                document.getElementById("tele-speed").innerText = `${tokSec} tok/s`;
                document.getElementById("tele-ttft").innerText = `${ttft} s`;
                document.getElementById("tele-latency").innerText = `${(elapsedSec * 1000).toFixed(0)} ms`;
              }
            } catch (e) {}
          }
        }
      }

      // Save Assistant response to DB
      if (fullText) {
        await fetch(`/api/v1/conversations/${currentConvId}/messages`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            role: "assistant",
            content: fullText,
            metrics: { tokens: totalTokens, ttft: firstTokenTime }
          })
        });
        activeMessages.push({ role: "assistant", content: fullText });
      }

    } catch (e) {
      if (e.name !== 'AbortError') {
        assistantBubble.innerText = `[Error] Inference stream error: ${e.message}`;
      }
    } finally {
      toggleGeneratingState(false);
      currentAbortController = null;
    }
  }

  function max(a, b) { return a > b ? a : b; }

  // Hardware Metrics
  async function fetchHardwareMetrics() {
    try {
      const res = await fetch("/api/v1/hardware");
      const metrics = await res.json();

      document.getElementById("cpu-val").innerText = `${metrics.cpu_percent}%`;
      document.getElementById("cpu-bar").style.width = `${metrics.cpu_percent}%`;

      document.getElementById("ram-val").innerText = `${metrics.ram_used_gb} / ${metrics.ram_total_gb} GB`;
      document.getElementById("ram-bar").style.width = `${metrics.ram_percent}%`;

      document.getElementById("vram-val").innerText = `${metrics.vram_used_gb} / ${metrics.vram_total_gb} GB`;
      document.getElementById("vram-bar").style.width = `${metrics.vram_percent}%`;

      document.getElementById("disk-val").innerText = `R: ${metrics.disk_read_mbs} MB/s | W: ${metrics.disk_write_mbs} MB/s`;
      document.getElementById("disk-sub").innerText = `Storage Free: ${metrics.disk_free_gb} GB / ${metrics.disk_total_gb} GB`;
    } catch (e) {}
  }

  // Models List
  async function fetchModels() {
    try {
      const res = await fetch("/api/v1/models");
      const models = await res.json();
      const grid = document.getElementById("models-grid");
      grid.innerHTML = "";

      models.forEach(m => {
        const card = document.createElement("div");
        card.className = "model-card";
        card.innerHTML = `
          <div class="model-card-title">${m.name}</div>
          <div class="model-meta">Family: ${m.family}</div>
          <div class="model-meta">Params: ${m.total_params} (Active: ${m.active_params})</div>
          <div class="model-meta">Quant: ${m.quantization} | Disk: ${m.disk_size_gb} GB</div>
          <div class="model-meta">RAM Required: ${m.required_ram_gb} GB</div>
          <button class="btn btn-secondary btn-sm" onclick="selectModel('${m.id}')">Select Active</button>
        `;
        grid.appendChild(card);
      });
    } catch (e) {}
  }

  window.selectModel = async (id) => {
    await fetch("/api/v1/models/select", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model_id: id })
    });
    document.getElementById("active-model-badge").innerText = id;
  };

  // Settings
  async function loadSettings() {
    try {
      const res = await fetch("/api/v1/config");
      const cfg = await res.json();
      document.getElementById("cfg-exec").value = cfg.colibri_exec_path;
      document.getElementById("cfg-model-dir").value = cfg.model_dir;
      document.getElementById("cfg-host").value = cfg.api_host;
      document.getElementById("cfg-port").value = cfg.api_port;
    } catch (e) {}
  }

  document.getElementById("save-settings-btn").onclick = async () => {
    const payload = {
      colibri_exec_path: document.getElementById("cfg-exec").value,
      model_dir: document.getElementById("cfg-model-dir").value,
      api_host: document.getElementById("cfg-host").value,
      api_port: parseInt(document.getElementById("cfg-port").value)
    };
    await fetch("/api/v1/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    alert("Settings saved successfully.");
  };

  // Planner
  document.getElementById("run-planner-btn").onclick = async () => {
    const payload = {
      model_family: document.getElementById("plan-model").value,
      ram_gb: parseFloat(document.getElementById("plan-ram").value),
      vram_gb: parseFloat(document.getElementById("plan-vram").value),
      disk_free_gb: parseFloat(document.getElementById("plan-disk").value),
      storage_type: document.getElementById("plan-storage").value
    };

    const res = await fetch("/api/v1/planner", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const result = await res.json();

    const ratingEl = document.getElementById("plan-rating");
    ratingEl.innerText = result.rating;
    document.getElementById("plan-reasoning").innerText = result.reasoning;

    const listEl = document.getElementById("plan-bottlenecks");
    listEl.innerHTML = "";
    result.bottlenecks.forEach(b => {
      const li = document.createElement("li");
      li.innerText = b;
      listEl.appendChild(li);
    });
  };

  // Canvas Brain Visualization
  function renderBrainCanvas() {
    const canvas = document.getElementById("brain-canvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const cols = 40;
    const rows = 20;
    const cellW = canvas.width / cols;
    const cellH = canvas.height / rows;

    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const rand = Math.random();
        ctx.fillStyle = rand > 0.85 ? "#00f0ff" : rand > 0.4 ? "#0072ff" : "#3b1e7b";
        ctx.fillRect(c * cellW + 2, r * cellH + 2, cellW - 4, cellH - 4);
      }
    }
  }
});
