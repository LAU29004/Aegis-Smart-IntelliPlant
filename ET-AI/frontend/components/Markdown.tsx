"use client";

import React from "react";

/**
 * Tiny markdown renderer — supports **bold**, *italic*, `code`,
 * # headings, - / * bullet lists, 1. numbered lists and paragraphs.
 * No dependencies, no raw HTML injection.
 */

function renderInline(text: string, keyPrefix: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  // tokens: **bold**, *italic*, `code`
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) {
      nodes.push(<strong key={`${keyPrefix}-b${i}`}>{tok.slice(2, -2)}</strong>);
    } else if (tok.startsWith("`")) {
      nodes.push(<code key={`${keyPrefix}-c${i}`}>{tok.slice(1, -1)}</code>);
    } else {
      nodes.push(<em key={`${keyPrefix}-i${i}`}>{tok.slice(1, -1)}</em>);
    }
    last = m.index + tok.length;
    i++;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

export default function Markdown({ text }: { text: string }) {
  const lines = text.split(/\r?\n/);
  const blocks: React.ReactNode[] = [];
  let listItems: string[] = [];
  let listType: "ul" | "ol" | null = null;
  let key = 0;

  const flushList = () => {
    if (listItems.length === 0) return;
    const items = listItems.map((item, idx) => (
      <li key={idx}>{renderInline(item, `li-${key}-${idx}`)}</li>
    ));
    blocks.push(
      listType === "ol" ? (
        <ol key={`list-${key++}`}>{items}</ol>
      ) : (
        <ul key={`list-${key++}`}>{items}</ul>
      )
    );
    listItems = [];
    listType = null;
  };

  for (const raw of lines) {
    const line = raw.trimEnd();
    const bullet = line.match(/^\s*[-*]\s+(.*)$/);
    const numbered = line.match(/^\s*\d+[.)]\s+(.*)$/);
    const heading = line.match(/^(#{1,4})\s+(.*)$/);

    if (bullet) {
      if (listType === "ol") flushList();
      listType = "ul";
      listItems.push(bullet[1]);
    } else if (numbered) {
      if (listType === "ul") flushList();
      listType = "ol";
      listItems.push(numbered[1]);
    } else {
      flushList();
      if (heading) {
        const level = Math.min(heading[1].length + 2, 4);
        blocks.push(
          React.createElement(
            `h${level}`,
            { key: `h-${key++}` },
            renderInline(heading[2], `h-${key}`)
          )
        );
      } else if (line.trim() === "") {
        // blank line — paragraph separator, nothing to emit
      } else {
        blocks.push(
          <p key={`p-${key++}`}>{renderInline(line, `p-${key}`)}</p>
        );
      }
    }
  }
  flushList();

  return <div className="md">{blocks}</div>;
}
