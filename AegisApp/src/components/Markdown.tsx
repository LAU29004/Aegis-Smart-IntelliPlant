import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { colors, spacing, typography } from '../theme/colors';

/**
 * Tiny markdown renderer — supports **bold**, *italic*, `code`,
 * # headings, - / * bullet lists, 1. numbered lists and paragraphs.
 * No dependencies, no raw HTML injection. RN port of the web Markdown.tsx.
 */

function renderInline(text: string, keyPrefix: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith('**')) {
      nodes.push(
        <Text key={`${keyPrefix}-b${i}`} style={styles.bold}>
          {tok.slice(2, -2)}
        </Text>,
      );
    } else if (tok.startsWith('`')) {
      nodes.push(
        <Text key={`${keyPrefix}-c${i}`} style={styles.code}>
          {' '}{tok.slice(1, -1)}{' '}
        </Text>,
      );
    } else {
      nodes.push(
        <Text key={`${keyPrefix}-i${i}`} style={styles.italic}>
          {tok.slice(1, -1)}
        </Text>,
      );
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
  let listType: 'ul' | 'ol' | null = null;
  let key = 0;

  const flushList = () => {
    if (listItems.length === 0) return;
    const items = listItems;
    const type = listType;
    blocks.push(
      <View key={`list-${key++}`} style={styles.list}>
        {items.map((item, idx) => (
          <View key={idx} style={styles.listItem}>
            <Text style={styles.listBullet}>{type === 'ol' ? `${idx + 1}.` : '•'}</Text>
            <Text style={styles.listText}>{renderInline(item, `li-${key}-${idx}`)}</Text>
          </View>
        ))}
      </View>,
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
      if (listType === 'ol') flushList();
      listType = 'ul';
      listItems.push(bullet[1]);
    } else if (numbered) {
      if (listType === 'ul') flushList();
      listType = 'ol';
      listItems.push(numbered[1]);
    } else {
      flushList();
      if (heading) {
        const level = Math.min(heading[1].length, 4);
        blocks.push(
          <View key={`hwrap-${key}`} style={headingWrap(level)}>
            <Text style={[styles.heading, headingSize(level)]}>
              {renderInline(heading[2], `h-${key++}`)}
            </Text>
            {level === 1 && <View style={styles.headingRule} />}
          </View>,
        );
      } else if (line.trim() === '') {
        // blank line — paragraph separator
      } else {
        blocks.push(
          <Text key={`p-${key++}`} style={styles.body}>
            {renderInline(line, `p-${key}`)}
          </Text>,
        );
      }
    }
  }
  flushList();

  return <View style={styles.md}>{blocks}</View>;
}

function headingSize(level: number) {
  const sizes = [20, 18, 16, 15];
  return { fontSize: sizes[level - 1] ?? 15 };
}

function headingWrap(level: number) {
  return { marginTop: level === 1 ? 10 : 6, gap: 4 };
}

const styles = StyleSheet.create({
  md: { gap: spacing.md },
  body: { ...typography.body, color: colors.textPrimary, lineHeight: 22 },
  heading: { color: colors.textPrimary, fontWeight: '700', letterSpacing: 0.1 },
  headingRule: {
    height: 1,
    backgroundColor: colors.border,
    marginTop: 2,
  },
  bold: { fontWeight: '700', color: colors.textPrimary },
  italic: { fontStyle: 'italic', color: colors.textSecondary },
  code: {
    fontFamily: 'Menlo',
    fontSize: 13,
    backgroundColor: colors.surface3,
    color: colors.accent,
    borderRadius: 4,
    overflow: 'hidden',
  },
  list: { gap: 6 },
  listItem: { flexDirection: 'row', gap: 8, alignItems: 'flex-start', paddingLeft: 2 },
  listBullet: { color: colors.accent, fontWeight: '700', width: 18, lineHeight: 22 },
  listText: { ...typography.body, color: colors.textPrimary, lineHeight: 22, flex: 1 },
});