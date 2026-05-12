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
  let lastYamlErr = "";

  function domOk() {
    return !!(app && notice && sidebar && searchEl && tocEl && meta);
  }

  if (!domOk()) {
    document.body.insertAdjacentHTML(
      "afterbegin",
      '<p class="notice err" style="margin:1rem;">页面 DOM 不完整（需 #app #notice #sidebar #search #toc）。请更新插件中的 web/static 文件后重试。</p>'
    );
    return;
  }

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
    if (t.charCodeAt(0) === 0xfeff) {
      t = t.slice(1).trim();
    }
    if (t.startsWith("```")) {
      const lines = t.split(/\n/);
      if (lines.length && lines[0].startsWith("```")) lines.shift();
      if (lines.length && lines[lines.length - 1].trim() === "```") lines.pop();
      t = lines.join("\n").trim();
    }
    return t;
  }

  function taskbookVersionIsV1(v) {
    if (v === true || v === false) return false;
    if (v === null || v === undefined) return false;
    if (typeof v === "string" && v.trim() === "") return false;
    const n = Number(v);
    return !isNaN(n) && n === 1;
  }

  function tryParseYamlTaskbook(raw) {
    lastYamlErr = "";
    if (typeof jsyaml === "undefined" || !jsyaml.load) {
      lastYamlErr = "js-yaml 未加载";
      return null;
    }
    const text = stripLeadingFence(raw);
    if (!text) {
      lastYamlErr = "内容为空";
      return null;
    }
    try {
      const doc = jsyaml.load(text);
      if (
        doc &&
        typeof doc === "object" &&
        taskbookVersionIsV1(doc.version) &&
        Array.isArray(doc.tree)
      ) {
        return doc;
      }
      lastYamlErr =
        "根节点不符合 v1（需要可转为数字 1 的 version 与数组 tree）。实际 version=" +
        JSON.stringify(doc && doc.version);
    } catch (e) {
      lastYamlErr = (e && e.message) || String(e);
    }
    return null;
  }

  function nodeKind(node) {
    return String((node && node.kind) || "")
      .trim()
      .toLowerCase();
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

  /** 从 contributors 文本中解析 @login，顺序去重，用于 GitHub 头像 */
  function parseGitHubLoginsFromContributors(text) {
    const re = /@([a-zA-Z0-9](?:-?[a-zA-Z0-9]){0,38})/g;
    const seen = {};
    const out = [];
    let m;
    const s = String(text || "");
    while ((m = re.exec(s)) !== null) {
      const login = m[1];
      if (!seen[login]) {
        seen[login] = true;
        out.push(login);
      }
    }
    return out;
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
    let contribInner = "";
    if (!contribEmpty) {
      const logins = parseGitHubLoginsFromContributors(contribution);
      const avatarParts = [];
      if (logins.length) {
        avatarParts.push('<div class="contrib-avatars">');
        for (let j = 0; j < logins.length; j++) {
          const login = logins[j];
          const src =
            "https://github.com/" + encodeURIComponent(login) + ".png?size=96";
          avatarParts.push(
            '<img class="contrib-avatar" src="' +
              escAttr(src) +
              '" alt="@' +
              escAttr(login) +
              '" title="@' +
              escAttr(login) +
              '" width="40" height="40" loading="lazy" referrerpolicy="no-referrer" />'
          );
        }
        avatarParts.push("</div>");
      }
      contribInner =
        avatarParts.join("") +
        '<div class="contrib-text">' +
        esc(contribution) +
        "</div>";
    }
    h.push('<div class="' + contribClass + '">' + contribInner + "</div>");
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
      const kind = nodeKind(node);
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
      if (nodeKind(node) === "section") {
        const t = String(node.title || "");
        const next = stack.concat(t);
        const search = yamlSectionSearchStack(next);
        html += '<li class="toc-section" data-search="' + escAttr(search) + '">';
        html += '<span class="toc-section-label">' + esc(t) + "</span>";
        html += buildTocFromNodes(node.children || [], next);
        html += "</li>";
      } else if (nodeKind(node) === "task") {
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
    for (let c = 0; c < ul.children.length; c++) {
      const li = ul.children[c];
      if (li.tagName !== "LI") continue;
      let nested = null;
      for (let j = 0; j < li.children.length; j++) {
        const ch = li.children[j];
        if (ch.tagName === "UL" && ch.classList.contains("toc-tree")) {
          nested = ch;
          break;
        }
      }
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
    if (!app) return;
    const cards = app.querySelectorAll("article.card");
    cards.forEach(function (card) {
      const hay = card.dataset.search || "";
      const ok = matchesSearch(hay, queryTrimmed);
      card.classList.toggle("search-hide", !ok);
    });
    if (!tocEl) return;
    const rootUl = tocEl.querySelector("ul.toc-tree");
    filterTocRecursive(rootUl, queryTrimmed);
  }

  function buildTocYaml(doc) {
    if (!tocEl) return;
    const inner = buildTocFromNodes(doc.tree || [], []);
    tocEl.innerHTML = '<div class="toc-title">目录</div>' + inner;
  }

  function bindToolbar() {
    if (toolbarBound || !searchEl || !tocEl) return;
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
    if (!sidebar || !searchEl || !tocEl) return;
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
    try {
      let res;
      try {
        res = await fetch("/api/taskbook?token=" + encodeURIComponent(token), {
          cache: "no-store",
        });
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
        const inner = renderTreeNodes(yamlDoc.tree || [], 0, []);
        if (!inner || !String(inner).trim()) {
          app.innerHTML =
            '<p class="notice">已解析 YAML v1，但 <code>tree</code> 为空或没有可识别的 <code>section</code>/<code>task</code> 节点（请检查 <code>kind</code> 拼写）。</p>';
          setSidebarVisible(false);
          return;
        }
        let html = '<div class="items yaml-items">';
        html += inner;
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
      if (typeof jsyaml === "undefined" || !jsyaml.load) {
        errHtml +=
          '<p class="notice err yaml-miss">未加载 js-yaml（请确认 /static/js-yaml.min.js 存在且未被拦截）。</p>';
      } else {
        errHtml +=
          '<p class="notice err">无法作为 YAML v1 任务书解析。</p>' +
          (lastYamlErr
            ? '<p class="notice err parse-detail"><strong>原因：</strong>' +
              esc(lastYamlErr) +
              "</p>"
            : "") +
          '<p class="notice">请确认 Gist 正文以 <code>version: 1</code> 与 <code>tree:</code> 开头，或在机器人侧 <code>/watcher organize</code>。</p>';
      }
      app.innerHTML = errHtml;
      setSidebarVisible(false);
    } catch (err) {
      app.innerHTML =
        '<p class="notice err">页面脚本异常：' +
        esc((err && err.message) || String(err)) +
        "</p>";
      setSidebarVisible(false);
    }
  }

  load();
})();
