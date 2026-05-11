(function () {
  const params = new URLSearchParams(window.location.search);
  const token = params.get("token");
  const meta = document.getElementById("meta");
  const app = document.getElementById("app");
  const notice = document.getElementById("notice");
  const toolbar = document.getElementById("toolbar");
  const searchEl = document.getElementById("search");
  const tocEl = document.getElementById("toc");

  let searchDebounce = null;
  let toolbarBound = false;

  function esc(s) {
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  function isBlank(s) {
    return !s || !String(s).trim();
  }

  function parseTaskbookMarkdown(md) {
    const lines = md.split(/\r?\n/);
    const items = [];
    const preamble = [];
    let i = 0;

    while (i < lines.length) {
      const m = lines[i].match(/^##\s+(\d+)\.\s*(.*)$/);
      if (m) {
        const num = m[1];
        const titleLine = m[2].trim();
        i++;
        const body = [];
        while (i < lines.length && !/^##\s+\d+\./.test(lines[i])) {
          body.push(lines[i]);
          i++;
        }
        items.push({ num, title: titleLine, body: body.join("\n").trim() });
        continue;
      }
      preamble.push(lines[i]);
      i++;
    }
    return { preamble: preamble.join("\n").trim(), items };
  }

  function bulletField(body, label) {
    const re = new RegExp(
      "^\\s*-\\s*\\*\\*" + label + "：\\*\\*\\s*(.*)$",
      "im"
    );
    const m = body.match(re);
    return m ? m[1].trim().replace(/^`+|`+$/g, "") : "";
  }

  function extractContribution(body) {
    return (
      bulletField(body, "贡献") ||
      bulletField(body, "贡献者") ||
      bulletField(body, "主要贡献")
    );
  }

  function extractCompletion(body) {
    return (
      bulletField(body, "具体完成了什么内容") ||
      bulletField(body, "完成情况")
    );
  }

  function stripKnownLines(body) {
    return body
      .split(/\r?\n/)
      .filter(function (line) {
        return !/^\s*-\s*\*\*(条目|具体完成了什么内容|完成情况|贡献|贡献者|主要贡献|关联路径)：\*\*/.test(
          line
        );
      })
      .join("\n")
      .trim();
  }

  function itemSearchText(item) {
    const body = item.body;
    return [
      item.num,
      item.title,
      bulletField(body, "条目"),
      bulletField(body, "关联路径"),
      extractContribution(body),
      extractCompletion(body),
      stripKnownLines(body),
    ]
      .filter(function (x) {
        return x && String(x).trim();
      })
      .join("\n")
      .toLowerCase();
  }

  function renderItem(item) {
    const body = item.body;
    const entry = bulletField(body, "条目");
    const paths = bulletField(body, "关联路径");
    const contribution = extractContribution(body);
    const completion = extractCompletion(body);
    const stripKnown = stripKnownLines(body);

    const contribEmpty = isBlank(contribution);
    const completeEmpty = isBlank(completion);

    const contribClass = "detail-body" + (contribEmpty ? " is-empty" : "");
    const completeClass = "detail-body" + (completeEmpty ? " is-empty" : "");

    const h = [];
    h.push('<article class="card" id="task-' + item.num + '">');
    h.push('<div class="card-head">');
    h.push("<h2>" + esc(item.num + ". " + (item.title || "（无标题）")) + "</h2>");
    if (entry) {
      h.push(
        '<p class="field"><span class="label">条目</span>' + esc(entry) + "</p>"
      );
    }
    if (paths) {
      h.push(
        '<p class="field"><span class="label">关联路径</span> <code>' +
          esc(paths) +
          "</code></p>"
      );
    }
    h.push("</div>");

    h.push('<details class="item-details">');
    h.push("<summary>贡献与完成情况</summary>");
    h.push('<div class="detail-panel">');
    h.push('<div class="detail-block">');
    h.push("<h4>贡献</h4>");
    h.push(
      '<div class="' + contribClass + '">' + (contribEmpty ? "" : esc(contribution)) + "</div>"
    );
    h.push("</div>");
    h.push('<div class="detail-block">');
    h.push("<h4>完成情况</h4>");
    h.push(
      '<div class="' +
        completeClass +
        '">' +
        (completeEmpty ? "" : esc(completion)) +
        "</div>"
    );
    h.push("</div>");
    h.push("</div>");
    h.push("</details>");

    if (stripKnown) {
      h.push('<div class="card-extra"><pre>' + esc(stripKnown) + "</pre></div>");
    }
    h.push("</article>");
    return h.join("");
  }

  /** 空格分词，全部子串都命中才算匹配（不区分大小写已在 haystack 侧） */
  function matchesSearch(haystackLower, queryTrimmed) {
    if (!queryTrimmed) return true;
    const parts = queryTrimmed.toLowerCase().split(/\s+/).filter(Boolean);
    if (!parts.length) return true;
    return parts.every(function (p) {
      return haystackLower.includes(p);
    });
  }

  function applySearch(queryTrimmed) {
    const cards = app.querySelectorAll("article.card");
    cards.forEach(function (card) {
      const hay = card.dataset.search || "";
      const ok = matchesSearch(hay, queryTrimmed);
      card.classList.toggle("search-hide", !ok);
    });
  }

  function buildToc(items) {
    let html =
      '<div class="toc-title">目录</div><ul class="toc-list">';
    for (let i = 0; i < items.length; i++) {
      const it = items[i];
      const label = it.num + ". " + (it.title || "（无标题）");
      html +=
        '<li><a href="#task-' + it.num + '">' + esc(label) + "</a></li>";
    }
    html += "</ul>";
    tocEl.innerHTML = html;
  }

  function bindToolbar() {
    if (toolbarBound) return;
    toolbarBound = true;

    searchEl.addEventListener("input", function () {
      const raw = searchEl.value;
      clearTimeout(searchDebounce);
      searchDebounce = setTimeout(function () {
        applySearch(raw.trim());
      }, 120);
    });

    tocEl.addEventListener("click", function (e) {
      const a = e.target.closest("a[href^='#']");
      if (!a) return;
      e.preventDefault();
      searchEl.value = "";
      applySearch("");
      const id = a.getAttribute("href").slice(1);
      const el = document.getElementById(id);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
  }

  function setToolbarVisible(show) {
    toolbar.classList.toggle("is-hidden", !show);
    toolbar.setAttribute("aria-hidden", show ? "false" : "true");
    if (!show) {
      searchEl.value = "";
      tocEl.innerHTML = "";
    }
  }

  function attachSearchIndex(items) {
    const cards = app.querySelectorAll("article.card");
    items.forEach(function (it, i) {
      const el = cards[i];
      if (el) {
        el.dataset.search = itemSearchText(it);
      }
    });
  }

  async function load() {
    if (!token) {
      return;
    }
    notice.style.display = "none";
    setToolbarVisible(false);
    app.innerHTML = '<p class="notice">加载中…</p>';
    let res;
    try {
      res = await fetch("/api/taskbook?token=" + encodeURIComponent(token));
    } catch (e) {
      app.innerHTML =
        '<p class="notice err">无法连接后端（请确认插件已启动且 web_server_port 已配置）。</p>';
      return;
    }
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.ok) {
      app.innerHTML =
        '<p class="notice err">加载失败：' +
        esc(data.error || "HTTP " + res.status) +
        "</p>";
      return;
    }
    meta.textContent =
      "来源：" +
      (data.source === "gist" ? "Gist（实时）" : "本地缓存") +
      (data.gist_url ? " · " + data.gist_url : "");

    const md = data.markdown || "";
    const parsed = parseTaskbookMarkdown(md);
    let html = "";
    if (parsed.items.length) {
      if (parsed.preamble) {
        html += '<div class="preamble">' + esc(parsed.preamble) + "</div>";
      }
      html += '<div class="items">';
      for (let j = 0; j < parsed.items.length; j++) {
        html += renderItem(parsed.items[j]);
      }
      html += "</div>";
    } else {
      html += '<div class="preamble raw">' + esc(md || "（空任务书）") + "</div>";
    }
    app.innerHTML = html;

    if (parsed.items.length) {
      attachSearchIndex(parsed.items);
      buildToc(parsed.items);
      setToolbarVisible(true);
      bindToolbar();
    } else {
      setToolbarVisible(false);
    }
  }

  load();
})();
