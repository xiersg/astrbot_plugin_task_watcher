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

  var HM_DAY_MS = 86400000;
  var hmTooltipEl = null;
  var hmModalEl = null;
  var hmModalKeyHandler = null;

  function ensureHmTooltip() {
    if (hmTooltipEl) return hmTooltipEl;
    hmTooltipEl = document.createElement("div");
    hmTooltipEl.className = "hm-tooltip";
    hmTooltipEl.setAttribute("role", "tooltip");
    hmTooltipEl.style.pointerEvents = "none";
    document.body.appendChild(hmTooltipEl);
    return hmTooltipEl;
  }

  function hideHmTooltip() {
    if (hmTooltipEl) {
      hmTooltipEl.style.opacity = "0";
      hmTooltipEl.style.visibility = "hidden";
    }
  }

  function hmLevelFor(count, maxA) {
    var c = count || 0;
    if (c <= 0 || maxA <= 0) return 0;
    var r = c / maxA;
    if (r <= 0.25) return 1;
    if (r <= 0.5) return 2;
    if (r <= 0.75) return 3;
    return 4;
  }

  function hmParseDay(s) {
    var p = String(s || "").split("-");
    if (p.length !== 3) return NaN;
    return Date.UTC(+p[0], +p[1] - 1, +p[2]);
  }

  function hmUtcDayKey(ms) {
    return new Date(ms).toISOString().slice(0, 10);
  }

  function hmBuildWeekColumns(rangeStartStr, rangeEndStr, daysMap, maxA) {
    var start = hmParseDay(rangeStartStr);
    var end = hmParseDay(rangeEndStr);
    if (isNaN(start) || isNaN(end)) return [];
    var startDow = new Date(start).getUTCDay();
    start -= startDow * HM_DAY_MS;
    var endDow = new Date(end).getUTCDay();
    var endPad = end + (6 - endDow) * HM_DAY_MS;
    var cols = [];
    for (var t = start; t <= endPad; t += 7 * HM_DAY_MS) {
      var col = [];
      for (var r = 0; r < 7; r++) {
        var ts = t + r * HM_DAY_MS;
        var key = hmUtcDayKey(ts);
        var inRange = key >= rangeStartStr && key <= rangeEndStr;
        var d = daysMap && daysMap[key] ? daysMap[key] : null;
        var count = d ? (d.commit_count || 0) + (d.pr_count || 0) : 0;
        var level = inRange ? hmLevelFor(count, maxA) : 0;
        col.push({ ts: ts, key: key, inRange: inRange, count: count, level: level, day: d });
      }
      cols.push(col);
    }
    return cols;
  }

  function hmRankRows(by_login) {
    var rows = [];
    if (!by_login || typeof by_login !== "object") return rows;
    for (var login in by_login) {
      if (!Object.prototype.hasOwnProperty.call(by_login, login)) continue;
      var o = by_login[login];
      var c = o.commits || 0;
      var p = o.prs || 0;
      rows.push({ login: login, c: c, p: p, t: c + p });
    }
    rows.sort(function (a, b) {
      if (b.t !== a.t) return b.t - a.t;
      if (b.c !== a.c) return b.c - a.c;
      return String(a.login).localeCompare(String(b.login));
    });
    return rows;
  }

  function renderHeatmapHTML(data) {
    var maxA = data.max_activity || 0;
    if (maxA < 1) maxA = 1;
    var cols = hmBuildWeekColumns(
      data.range_start,
      data.range_end,
      data.days || {},
      maxA
    );
    var h = [];
    h.push('<div class="hm-inner">');
    h.push('<div class="hm-head">');
    h.push('<h2 class="hm-title">贡献热力图</h2>');
    h.push(
      '<p class="hm-meta"><span class="hm-repo">' +
        esc(data.repo || "") +
        "</span> · <span>" +
        esc(data.range_start || "") +
        " ~ " +
        esc(data.range_end || "") +
        "</span></p>"
    );
    if (data.utc_note) h.push('<p class="hm-note">' + esc(data.utc_note) + "</p>");
    if (data.pr_search_truncated) {
      h.push(
        '<p class="hm-warn">部分 PR 可能因 GitHub Search 单次上限未完全列出；当日详情仍以已拉取数据为准。</p>'
      );
    }
    h.push("</div>");
    h.push('<div class="hm-grid-wrap" role="img" aria-label="贡献按日热力图">');
    h.push('<div class="hm-grid" role="presentation">');
    for (var ci = 0; ci < cols.length; ci++) {
      h.push('<div class="hm-week" role="presentation">');
      var col = cols[ci];
      for (var ri = 0; ri < col.length; ri++) {
        var cell = col[ri];
        var tip = cell.key;
        if (cell.inRange) {
          tip +=
            " · 提交 " +
            (cell.day ? cell.day.commit_count || 0 : 0) +
            " · PR " +
            (cell.day ? cell.day.pr_count || 0 : 0);
          var contribs = cell.day && cell.day.contributors ? cell.day.contributors : [];
          if (contribs.length) tip += " · " + contribs.map(function (x) { return "@" + x; }).join(" ");
        } else {
          tip += "（不在统计区间）";
        }
        h.push(
          '<div class="hm-cell hm-l' +
            cell.level +
            (cell.inRange ? "" : " hm-out") +
            '" data-date="' +
            escAttr(cell.key) +
            '" data-in-range="' +
            (cell.inRange ? "1" : "0") +
            '" tabindex="' +
            (cell.inRange ? "0" : "-1") +
            '" title="' +
            escAttr(tip) +
            '" role="' +
            (cell.inRange ? "button" : "presentation") +
            '" aria-label="' +
            escAttr(tip) +
            '"></div>'
        );
      }
      h.push("</div>");
    }
    h.push("</div></div>");
    h.push('<div class="hm-legend"><span class="hm-legend-lbl">少</span>');
    for (var lj = 0; lj < 5; lj++) {
      h.push('<span class="hm-leg hm-l' + lj + '" aria-hidden="true"></span>');
    }
    h.push('<span class="hm-legend-lbl">多</span></div>');
    h.push(
      '<p class="hm-hint">悬停查看当日贡献者；点击可查看排行榜与提交、PR 列表。</p>'
    );
    h.push("</div>");
    return h.join("");
  }

  function closeHmModal() {
    if (hmModalEl) {
      hmModalEl.remove();
      hmModalEl = null;
    }
    if (hmModalKeyHandler) {
      document.removeEventListener("keydown", hmModalKeyHandler);
      hmModalKeyHandler = null;
    }
  }

  function openHmModal(dateKey, data) {
    closeHmModal();
    var day = data && data.days && data.days[dateKey];
    var parts = [];
    parts.push('<div class="hm-modal" role="dialog" aria-modal="true" aria-labelledby="hm-modal-title">');
    parts.push('<div class="hm-modal-backdrop" data-hm-close="1"></div>');
    parts.push('<div class="hm-modal-panel">');
    parts.push(
      '<button type="button" class="hm-modal-close" data-hm-close="1" aria-label="关闭">×</button>'
    );
    parts.push('<h3 id="hm-modal-title">' + esc(dateKey) + "（UTC）</h3>");
    if (!day || ((day.commit_count || 0) === 0 && (day.pr_count || 0) === 0)) {
      parts.push('<p class="hm-modal-empty">当日无提交与已合并 PR。</p>');
    } else {
      parts.push(
        "<p>提交 <strong>" +
          esc(String(day.commit_count || 0)) +
          "</strong> 次 · 已合并 PR <strong>" +
          esc(String(day.pr_count || 0)) +
          "</strong> 个</p>"
      );
      var rows = hmRankRows(day.by_login || {});
      parts.push('<h4>贡献排行榜</h4>');
      parts.push('<table class="hm-rank-table"><thead><tr>');
      parts.push("<th>#</th><th>贡献者</th><th>提交</th><th>PR</th><th>合计</th></tr></thead><tbody>");
      for (var i = 0; i < rows.length; i++) {
        var r = rows[i];
        parts.push(
          "<tr><td>" +
            (i + 1) +
            "</td><td>" +
            esc(r.login) +
            "</td><td>" +
            r.c +
            "</td><td>" +
            r.p +
            "</td><td>" +
            r.t +
            "</td></tr>"
        );
      }
      parts.push("</tbody></table>");
      parts.push("<h4>提交</h4>");
      parts.push('<ul class="hm-link-list">');
      var commits = day.commits || [];
      if (!commits.length) {
        parts.push("<li>（无预览，可能超过单日展示条数）</li>");
      } else {
        for (var ci = 0; ci < commits.length; ci++) {
          var c = commits[ci];
          var href = c.html_url ? escAttr(c.html_url) : "";
          var line =
            '<code>' +
            esc((c.sha || "").slice(0, 7)) +
            "</code> · " +
            esc(c.login || "") +
            " — " +
            esc(c.message || "");
          if (href) {
            parts.push(
              '<li><a href="' + href + '" target="_blank" rel="noopener noreferrer">' + line + "</a></li>"
            );
          } else {
            parts.push("<li>" + line + "</li>");
          }
        }
      }
      parts.push("</ul>");
      parts.push("<h4>已合并 PR</h4>");
      parts.push('<ul class="hm-link-list">');
      var prs = day.prs || [];
      if (!prs.length) {
        parts.push("<li>（无预览，可能超过单日展示条数）</li>");
      } else {
        for (var pi = 0; pi < prs.length; pi++) {
          var pr = prs[pi];
          var ph = pr.html_url ? escAttr(pr.html_url) : "";
          var pline =
            "#" + esc(String(pr.number != null ? pr.number : "")) + " · " + esc(pr.title || "");
          if (ph) {
            parts.push(
              '<li><a href="' +
                ph +
                '" target="_blank" rel="noopener noreferrer">' +
                pline +
                "</a> · " +
                esc(pr.login || "") +
                "</li>"
            );
          } else {
            parts.push("<li>" + pline + " · " + esc(pr.login || "") + "</li>");
          }
        }
      }
      parts.push("</ul>");
    }
    parts.push("</div></div>");
    hmModalEl = document.createElement("div");
    hmModalEl.className = "hm-modal-root";
    hmModalEl.innerHTML = parts.join("");
    document.body.appendChild(hmModalEl);
    hmModalEl.addEventListener("click", function (e) {
      if (e.target && e.target.getAttribute && e.target.getAttribute("data-hm-close")) {
        closeHmModal();
      }
    });
    hmModalKeyHandler = function (e) {
      if (e.key === "Escape") closeHmModal();
    };
    document.addEventListener("keydown", hmModalKeyHandler);
  }

  function bindHeatmapInteractions(data, sectionEl) {
    window.__hmCalData = data;
    var tip = ensureHmTooltip();
    sectionEl.addEventListener("mousemove", function (e) {
      var cell = e.target.closest(".hm-cell");
      if (!cell || !sectionEl.contains(cell)) {
        hideHmTooltip();
        return;
      }
      var dk = cell.getAttribute("data-date") || "";
      var ir = cell.getAttribute("data-in-range") === "1";
      var text = dk;
      if (ir) {
        var day = data.days && data.days[dk];
        var cc = day ? day.commit_count || 0 : 0;
        var pc = day ? day.pr_count || 0 : 0;
        text += "\n提交 " + cc + " · PR " + pc;
        var cg = day && day.contributors ? day.contributors : [];
        if (cg.length) text += "\n" + cg.map(function (x) { return "@" + x; }).join(" ");
        else if (cc + pc > 0) text += "\n（贡献者见排行榜）";
      } else {
        text += "\n不在统计区间";
      }
      tip.textContent = text;
      tip.style.opacity = "1";
      tip.style.visibility = "visible";
      tip.style.left = Math.min(window.innerWidth - 220, e.clientX + 14) + "px";
      tip.style.top = Math.min(window.innerHeight - 80, e.clientY + 14) + "px";
    });
    sectionEl.addEventListener("mouseleave", function () {
      hideHmTooltip();
    });
    sectionEl.addEventListener("click", function (e) {
      var cell = e.target.closest(".hm-cell");
      if (!cell || !sectionEl.contains(cell)) return;
      if (cell.getAttribute("data-in-range") !== "1") return;
      var dateKey = cell.getAttribute("data-date");
      if (!dateKey) return;
      openHmModal(dateKey, window.__hmCalData || data);
    });
  }

  async function loadContributionsHeatmap(tok) {
    var sec = document.getElementById("contrib-heatmap-section");
    if (!sec || !tok) return;
    try {
      var res = await fetch(
        "/api/contributions?token=" + encodeURIComponent(tok) + "&days=371",
        { cache: "no-store" }
      );
      var payload = await res.json().catch(function () {
        return {};
      });
      if (!res.ok || !payload.ok) {
        sec.innerHTML =
          '<div class="hm-inner"><p class="notice err hm-msg">' +
          esc(payload.error || "HTTP " + res.status) +
          "</p></div>";
        return;
      }
      if (!payload.enabled) {
        sec.innerHTML =
          '<div class="hm-inner"><p class="notice hm-msg">' +
          esc(payload.message || "未配置监视仓库") +
          "</p></div>";
        return;
      }
      sec.innerHTML = renderHeatmapHTML(payload);
      bindHeatmapInteractions(payload, sec);
    } catch (err) {
      sec.innerHTML =
        '<div class="hm-inner"><p class="notice err hm-msg">' +
        esc((err && err.message) || String(err)) +
        "</p></div>";
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
        let html =
          '<section class="contrib-heatmap-section" id="contrib-heatmap-section"><div class="hm-inner"><p class="notice hm-loading">正在加载贡献热力图…</p></div></section>';
        html += '<div class="items yaml-items">';
        html += inner;
        html += "</div>";
        app.innerHTML = html;
        buildTocYaml(yamlDoc);
        setSidebarVisible(true);
        bindToolbar();
        applySearch("");
        loadContributionsHeatmap(token);
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
