/* A small Markdown subset for untrusted chat answers. No HTML, links or assets. */
(() => {
  "use strict";

  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
  const toneNames = new Set(["positive", "negative", "warning", "info", "muted"]);
  const fence = (line) => /^ {0,3}(`{3,}|~{3,})\s*([\w+-]*).*$/u.exec(line);
  const heading = (line) => /^ {0,3}(#{1,6})\s+(.+?)\s*#*\s*$/u.exec(line);
  const listItem = (line) => /^( {0,24})([-+*]|\d{1,9}[.)])\s+(.+)$/u.exec(line);
  const isRule = (line) => /^ {0,3}(?:(?:\*\s*){3,}|(?:-\s*){3,}|(?:_\s*){3,})$/u.test(line);

  function bracketPairs(text) {
    const pairs = new Map(), open = [];
    for (let index = 0; index < text.length; index++) {
      if (text[index] === "\\") { index++; continue; }
      if (text[index] === "`") {
        const run = /^`+/u.exec(text.slice(index))[0];
        const end = text.indexOf(run, index + run.length);
        index = end === -1 ? index + run.length - 1 : end + run.length - 1;
      } else if (text[index] === "[") open.push(index);
      else if (text[index] === "]" && open.length) pairs.set(open.pop(), index);
    }
    return pairs;
  }

  function inline(text, options, depth = 0) {
    if (depth > 8) return escapeHtml(text).replaceAll("\n", "<br>");
    let output = "", plain = "", index = 0;
    const pairs = text.includes(":") && text.includes("[") ? bracketPairs(text) : new Map();
    const flush = () => { output += escapeHtml(plain).replaceAll("\n", "<br>"); plain = ""; };
    while (index < text.length) {
      const char = text[index];
      if (char === "\\" && /[\\`*_{}[\]()#+.!|:>-]/u.test(text[index + 1] || "")) {
        plain += text[index + 1]; index += 2; continue;
      }
      if (char === "`") {
        const run = /^`+/u.exec(text.slice(index))[0];
        const end = text.indexOf(run, index + run.length);
        if (end !== -1) {
          flush(); output += `<code>${escapeHtml(text.slice(index + run.length, end))}</code>`;
          index = end + run.length; continue;
        }
        plain += run; index += run.length; continue;
      }
      if (char === ":") {
        const marker = /^:(positive|negative|warning|info|muted)\[/u.exec(text.slice(index, index + 12));
        if (marker && toneNames.has(marker[1])) {
          const start = index + marker[0].length;
          const end = pairs.get(start - 1);
          if (end !== undefined) {
            flush();
            const label = options.tones[marker[1]];
            output += `<span class="assistant-tone assistant-tone-${marker[1]}" title="${escapeHtml(label)}">${inline(text.slice(start, end), options, depth + 1)}</span>`;
            index = end + 1; continue;
          }
        }
      }
      if (char === "*" || char === "_") {
        const delimiter = text.startsWith(char + char, index) ? char + char : char;
        const start = index + delimiter.length;
        const end = text.indexOf(delimiter, start);
        const intraword = char === "_" && /[\p{L}\p{N}]/u.test(text[index - 1] || "");
        if (!intraword && end > start && !/^\s|\s$/u.test(text.slice(start, end))) {
          flush();
          const tag = delimiter.length === 2 ? "strong" : "em";
          output += `<${tag}>${inline(text.slice(start, end), options, depth + 1)}</${tag}>`;
          index = end + delimiter.length; continue;
        }
      }
      plain += char; index++;
    }
    flush(); return output;
  }

  function tableCells(line) {
    const source = line.trim();
    let buffer = "", codeTicks = 0;
    const cells = [];
    for (let index = 0; index < source.length; index++) {
      const char = source[index];
      if (char === "\\" && index + 1 < source.length) {
        buffer += source[index + 1] === "|" ? "|" : char + source[index + 1];
        index++; continue;
      }
      if (char === "`") {
        const run = /^`+/u.exec(source.slice(index))[0];
        codeTicks = !codeTicks ? run.length : codeTicks === run.length ? 0 : codeTicks;
        buffer += run; index += run.length - 1; continue;
      }
      if (char === "|" && !codeTicks) { cells.push(buffer.trim()); buffer = ""; }
      else buffer += char;
    }
    cells.push(buffer.trim());
    if (source.startsWith("|") && cells[0] === "") cells.shift();
    if (source.endsWith("|") && cells.at(-1) === "") cells.pop();
    return cells;
  }

  function tableDefinition(lines, index) {
    if (!lines[index]?.includes("|") || !lines[index + 1]) return null;
    const headers = tableCells(lines[index]);
    const separators = tableCells(lines[index + 1]);
    if (!headers.length || headers.length !== separators.length || !separators.every((cell) => /^:?-{3,}:?$/u.test(cell))) return null;
    return { headers, alignments: separators.map((cell) => cell.startsWith(":") && cell.endsWith(":") ? "center" : cell.endsWith(":") ? "right" : cell.startsWith(":") ? "left" : "start") };
  }

  function prettyJson(source) {
    if (source.length > 200_000) return source;
    try { JSON.parse(source); } catch { return source; }
    // Indent lexically: JSON.parse validates syntax but its rounded Number values
    // are never serialized. Number tokens and quoted strings remain byte-for-byte.
    let output = "", depth = 0, quoted = false, escaped = false, previous = "";
    const indent = () => "  ".repeat(Math.max(0, depth));
    for (let index = 0; index < source.length; index++) {
      const char = source[index];
      if (quoted) {
        output += char;
        if (escaped) escaped = false;
        else if (char === "\\") escaped = true;
        else if (char === '"') quoted = false;
        continue;
      }
      if (/\s/u.test(char)) continue;
      if (char === '"') { quoted = true; output += char; previous = char; continue; }
      if (char === "{" || char === "[") {
        output += char; depth++;
        if (depth > 64) return source;
        const next = /\S/u.exec(source.slice(index + 1))?.[0];
        if (next !== (char === "{" ? "}" : "]")) output += "\n" + indent();
      } else if (char === "}" || char === "]") {
        depth--;
        if (previous !== (char === "}" ? "{" : "[")) output += "\n" + indent();
        output += char;
      } else if (char === ",") output += ",\n" + indent();
      else if (char === ":") output += ": ";
      else output += char;
      previous = char;
      if (output.length > Math.min(1_000_000, source.length * 8 + 1024)) return source;
    }
    return output;
  }

  function blocks(lines, options, depth = 0) {
    if (depth > 8) return `<p>${escapeHtml(lines.join("\n")).replaceAll("\n", "<br>")}</p>`;
    let output = "", index = 0;
    const startsBlock = (position) => fence(lines[position]) || heading(lines[position]) || listItem(lines[position]) || /^ {0,3}>/u.test(lines[position]) || isRule(lines[position]) || tableDefinition(lines, position);
    while (index < lines.length) {
      const line = lines[index];
      if (!line.trim()) { index++; continue; }
      const codeFence = fence(line);
      if (codeFence) {
        const delimiter = codeFence[1][0], minimum = codeFence[1].length;
        const code = []; index++;
        while (index < lines.length) {
          const closing = lines[index].trim();
          if (closing.length >= minimum && [...closing].every((char) => char === delimiter)) { index++; break; }
          code.push(lines[index++]);
        }
        const language = codeFence[2].toLowerCase();
        const raw = code.join("\n");
        const content = language === "json" ? prettyJson(raw) : raw;
        output += `<div class="assistant-code-block">${language ? `<span class="assistant-code-language">${escapeHtml(language)}</span>` : ""}<pre tabindex="0" role="region" aria-label="${escapeHtml(options.codeLabel)}" dir="ltr"><code>${escapeHtml(content)}</code></pre></div>`;
        continue;
      }
      const title = heading(line);
      if (title) {
        const level = Math.min(title[1].length + 3, 6);
        output += `<h${level}>${inline(title[2], options)}</h${level}>`; index++; continue;
      }
      const table = tableDefinition(lines, index);
      if (table) {
        const start = index;
        const rows = []; index += 2;
        let oversized = table.headers.length > 32;
        while (index < lines.length && lines[index].trim() && lines[index].includes("|") && !fence(lines[index])) {
          if (!oversized) {
            const row = tableCells(lines[index]);
            rows.push(row);
            oversized = row.length > 32 || rows.length > 500;
          }
          index++;
        }
        const width = rows.reduce((largest, row) => Math.max(largest, row.length), table.headers.length);
        if (oversized || width * rows.length > 8000) {
          output += `<p class="assistant-format-fallback">${escapeHtml(lines.slice(start, index).join("\n")).replaceAll("\n", "<br>")}</p>`;
          continue;
        }
        const cell = (value) => `<bdi dir="auto">${inline(value || "", options)}</bdi>`;
        const alignment = (column) => `assistant-align-${table.alignments[column] || "start"}`;
        output += `<div class="assistant-table-wrap" role="region" tabindex="0" aria-label="${escapeHtml(options.tableLabel)}"><table><caption class="sr-only">${escapeHtml(options.tableLabel)}</caption><thead><tr>`;
        for (let column = 0; column < width; column++) output += `<th scope="col" class="${alignment(column)}">${cell(table.headers[column] || options.columnLabel.replace("{count}", String(column + 1)))}</th>`;
        output += "</tr></thead><tbody>";
        for (const row of rows) {
          output += "<tr>";
          for (let column = 0; column < width; column++) output += `<td class="${alignment(column)}">${cell(row[column])}</td>`;
          output += "</tr>";
        }
        output += "</tbody></table></div>"; continue;
      }
      if (/^ {0,3}>/u.test(line)) {
        const quote = [];
        while (index < lines.length && /^ {0,3}>/u.test(lines[index])) quote.push(lines[index++].replace(/^ {0,3}> ?/u, ""));
        output += `<blockquote>${blocks(quote, options, depth + 1)}</blockquote>`; continue;
      }
      if (isRule(line)) { output += "<hr>"; index++; continue; }
      const item = listItem(line);
      if (item) {
        const indent = item[1].length, ordered = /^\d/u.test(item[2]), tag = ordered ? "ol" : "ul";
        output += `<${tag}${ordered ? ` start="${item[2].slice(0, -1)}"` : ""}>`;
        while (index < lines.length) {
          const current = listItem(lines[index]);
          if (!current || current[1].length !== indent || /^\d/u.test(current[2]) !== ordered) break;
          const body = [current[3]]; index++;
          while (index < lines.length) {
            if (!lines[index].trim()) {
              const following = listItem(lines[index + 1] || "");
              if (following?.[1].length === indent) { index++; break; }
              if (!lines[index + 1] || /^ */u.exec(lines[index + 1])[0].length <= indent) break;
              body.push(""); index++; continue;
            }
            if (/^ */u.exec(lines[index])[0].length <= indent) break;
            body.push(lines[index++].slice(indent + 2));
          }
          output += `<li>${blocks(body, options, depth + 1)}</li>`;
        }
        output += `</${tag}>`; continue;
      }
      const paragraph = [line]; index++;
      while (index < lines.length && lines[index].trim() && !startsBlock(index)) paragraph.push(lines[index++]);
      output += `<p>${inline(paragraph.join("\n"), options)}</p>`;
    }
    return output;
  }

  function render(value, labels = {}) {
    const options = {
      tableLabel: String(labels.tableLabel || "Answer table"), codeLabel: String(labels.codeLabel || "Code block"),
      columnLabel: String(labels.columnLabel || "Column {count}"),
      tones: { positive: "Positive", negative: "Negative", warning: "Warning", info: "Information", muted: "Note", ...(labels.tones || {}) },
    };
    const source = String(value ?? "").replace(/\r\n?/g, "\n");
    if (source.length > 200_000) return `<p class="assistant-format-fallback">${escapeHtml(source).replaceAll("\n", "<br>")}</p>`;
    return blocks(source.split("\n"), options);
  }

  window.PortfolioAssistantFormat = Object.freeze({ render, prettyJson });
})();
