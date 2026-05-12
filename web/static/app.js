(function () {
  const params = new URLSearchParams(window.location.search);
  const token = params.get("token");
  const meta = document.getElementById("meta");
  const app = document.getElementById("app");
  const notice = document.getElementById("notice");
  const sidebar = document.getElementById("sidebar");
  const searchEl = document.getElementById("search");
  const tocEl = document.getElementById("toc");

  let searchDebounce = null;
  let toolbarBound = false;

  function esc(s) {
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  function escAttr(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/</g, "&lt;")
      .replace(/\n/g, " ");
  }

  function safeDomId(id) {
    return String(id || "task").replace(/[^a-zA-Z0-9_-]/g, "_");
  }

  function isBlank(s) {
    return !s || !String(s).trim();
  }

  function stripLeadingFence(text) {
    let t = (text || "").trim();
    if (t.startsWith("```")) {
      const lines = t.split(/\n/);
      if (lines.length && lines[0].startsWith("```")) lines.shift();
      if (lines.length && lines[lines.length - 1].trim() === "```") lines.pop();
      t = lines.join("\n").trim();
    }
    return t;
  }

  function tryParseYamlTaskbook(raw) {
    if (typeof jsyaml === "undefined") return null;
    const text = stripLeadingFence(raw);
    try {
      const doc = jsyaml.load(text);
      if (doc && doc.version === 1 && Array.isArray(doc.tree)) return doc;
    } catch (_e) {}
    return null;
  }

  function yamlTaskSearchText(node) {
    return [
      node.id,
      node.title,
      node.completion,
      node.description,
      node.contributors,
      node.paths,
    ]
      .filter(function (x) {
        return x && String(x).trim();
      })
      .join("\n")
      .toLowerCase();
  }

  function yamlSectionSearchStack(stack) {
    return stack.filter(Boolean).join(" ").toLowerCase();
  }

  function renderYamlTaskCard(node, depth, pathStack) {
    const title = String(node.title || "（无标题）");
    const sid = safeDomId(node.id);
    const desc = String(node.description || "").trim();
    const paths = String(node.paths || "").trim();
    const contribution = String(node.contributors || "").trim();
    const completion = String(node.completion || "").trim();
    const crumb = pathStack.filter(Boolean).join(" / ");

    const contribEmpty = isBlank(contribution);
    const completeEmpty = isBlank(completion);
    const descEmpty = isBlank(desc);

    const contribClass = "detail-body" + (contribEmpty ? " is-empty" : "");
    const completeClass = "detail-body" + (completeEmpty ? " is-empty" : "");
    const descClass = "detail-body" + (descEmpty ? " is-empty" : "");

    const h = [];
    h.push(
      '<article class="card yaml-task" id="task-' +
        sid +
        '" data-depth="' +
        depth +
        '" data-search="' +
        escAttr(yamlTaskSearchText(node)) +
        '">'
    );
    h.push('<div class="card-head">');
    h.push(
      "<h2>" +
        esc(title) +
        '</h2><p class="task-id"><code>' +
        esc(String(node.id || "")) +
        "</code></p>"
    );
    if (crumb) {
      h.push('<p class="field crumb"><span class="label">路径</span>' + esc(crumb) + "</p>");
    }
    if (paths) {
      h.push(
        '<p class="field"><span class="label">关联路径</span> <code>' +
          esc(paths) +
          "</code></p>"
      );
    }
    h.push("</div>");

    h.push('<details class="item-details" open>');
    h.push("<summary>描述、贡献与完成情况</summary>");
    h.push('<div class="detail-panel">');
    h.push('<div class="detail-block">');
    h.push("<h4>描述</h4>");
    h.push('<div class="' + descClass + '">' + (descEmpty ? "" : esc(desc)) + "</div>");
    h.push("</div>");
    h.push('<div class="detail-block">');
    h.push("<h4>贡献</h4>");
    h.push(
      '<div class="' + contribClass + '">' + (contribEmpty ? "" : esc(contribution)) + "</div>"
    );
    h.push("</div>");
    h.push('<div class="detail-block">');
    h.push("<h4>完成情况</h4>");
    h.push(
      '<div class="' + completeClass + '">' + (completeEmpty ? "" : esc(completion)) + "</div>"
    );
    h.push("</div>");
    h.push("</div>");
    h.push("</details>");

    h.push("</article>");
    return h.join("");
  }

  function renderTreeNodes(nodes, depth, pathStack) {
    const stack = pathStack || [];
    let html = "";
    const arr = nodes || [];
    for (let i = 0; i < arr.length; i++) {
      const node = arr[i];
      if (!node || typeof node !== "object") continue;
      const kind = node.kind;
      if (kind === "section") {
        const t = String(node.title || "");
        const nextStack = stack.concat(t);
        html += '<section class="tb-group" data-depth="' + depth + '">';
        html += '<h2 class="tb-section-title">' + esc(t) + "</h2>";
        html += '<div class="tb-group-body">';
        html += renderTreeNodes(node.children || [], depth + 1, nextStack);
        html += "</div></section>";
      } else if (kind === "task") {
        const t = String(node.title || "");
        const nextStack = stack.concat(t);
        html += renderYamlTaskCard(node, depth, nextStack);
        const kids = node.children;
        if (kids && kids.length) {
          html +=
            '<div class="tb-nested">' +
            renderTreeNodes(kids, depth + 1, nextStack) +
            "</div>";
        }
      }
    }
    return html;
  }

  function buildTocFromNodes(nodes, pathStack) {
    const stack = pathStack || [];
    let html = '<ul class="toc-tree" role="list">';
    const arr = nodes || [];
    for (let i = 0; i < arr.length; i++) {
      const node = arr[i];
      if (!node || typeof node !== "object") continue;
      if (node.kind === "section") {
        const t = String(node.title || "");
        const next = stack.concat(t);
        const search = yamlSectionSearchStack(next);
        html += '<li class="toc-section" data-search="' + escAttr(search) + '">';
        html += '<span class="toc-section-label">' + esc(t) + "</span>";
        html += buildTocFromNodes(node.children || [], next);
        html += "</li>";
      } else if (node.kind === "task") {
        const t = String(node.title || "");
        const next = stack.concat(t);
        const sid = safeDomId(node.id);
        const search = [
          yamlSectionSearchStack(next),
          node.completion,
          node.description,
          node.contributors,
          node.paths,
        ]
          .filter(function (x) {
            return x && String(x).trim();
          })
          .join("\n")
          .toLowerCase();
        const label = next.length > 1 ? next.slice(1).join(" / ") : t;
        html += '<li class="toc-task" data-search="' + escAttr(search) + '">';
        html +=
          '<a href="#task-' +
          sid +
          '">' +
          esc(label || t) +
          "</a>";
        const kids = node.children;
        if (kids && kids.length) html += buildTocFromNodes(kids, next);
        html += "</li>";
      }
    }
    html += "</ul>";
    return html;
  }

  function matchesSearch(haystackLower, queryTrimmed) {
    if (!queryTrimmed) return true;
    const parts = queryTrimmed.toLowerCase().split(/\s+/).filter(Boolean);
    if (!parts.length) return true;
    return parts.every(function (p) {
      return haystackLower.includes(p);
    });
  }

  function filterTocRecursive(ul, queryTrimmed) {
    if (!ul) return false;
    let anyVisible = false;
    const lis = ul.querySelectorAll(":scope > li");
    for (let i = 0; i < lis.length; i++) {
      const li = lis[i];
      const nested = li.querySelector(":scope > ul.toc-tree");
      let childAny = false;
      if (nested) childAny = filterTocRecursive(nested, queryTrimmed);
      const hay = (li.getAttribute("data-search") || "").toLowerCase();
      const selfOk = matchesSearch(hay, queryTrimmed);
      const show = !queryTrimmed || selfOk || childAny;
      li.classList.toggle("toc-hide", !show);
      if (show) anyVisible = true;
    }
    return anyVisible;
  }

  function applySearch(queryTrimmed) {
    const cards = app.querySelectorAll("article.card");
    cards.forEach(function (card) {
      const hay = card.dataset.search || "";
      const ok = matchesSearch(hay, queryTrimmed);
      card.classList.toggle("search-hide", !ok);
    });
    const rootUl = tocEl.querySelector("ul.toc-tree");
    filterTocRecursive(rootUl, queryTrimmed);
  }

  function buildTocYaml(doc) {
    const inner = buildTocFromNodes(doc.tree || [], []);
    tocEl.innerHTML = '<div class="toc-title">目录</div>' + inner;
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

  function setSidebarVisible(show) {
    sidebar.classList.toggle("is-hidden", !show);
    sidebar.setAttribute("aria-hidden", show ? "false" : "true");
    if (!show) {
      searchEl.value = "";
      tocEl.innerHTML = "";
    }
  }

  async function load() {
    if (!token) {
      return;
    }
    notice.style.display = "none";
    setSidebarVisible(false);
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

    const raw = data.taskbook || data.markdown || "";
    const yamlDoc = tryParseYamlTaskbook(raw);

    if (yamlDoc) {
      let html = '<div class="items yaml-items">';
      html += renderTreeNodes(yamlDoc.tree || [], 0, []);
      html += "</div>";
      app.innerHTML = html;
      buildTocYaml(yamlDoc);
      setSidebarVisible(true);
      bindToolbar();
      applySearch("");
      return;
    }

    let errHtml =
      '<div class="preamble raw">' + esc(raw || "（空）") + "</div>";
    if (typeof jsyaml === "undefined") {
      errHtml +=
        '<p class="notice err yaml-miss">未加载 js-yaml（CDN），无法解析任务书。请检查网络后刷新。</p>';
    } else {
      errHtml +=
        '<p class="notice err">任务书必须是有效的 YAML v1（含 <code>version: 1</code> 与 <code>tree:</code>）。请在机器人侧执行 <code>/watcher organize</code> 或重新 <code>/watcher set_gist</code>。</p>';
    }
    app.innerHTML = errHtml;
    setSidebarVisible(false);
  }

  load();
})();
