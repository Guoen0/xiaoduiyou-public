# Process document Markdown fidelity

Use this when Xiaoduiyou content packages or ordinary documents preserve original Markdown/Feishu source material under `过程文档`.

## Expected behavior

The process document is a fidelity/QA surface. The user expects original headings, lists, images, and tables to remain visually recognizable.

- Paragraph text matching `#` / `##` headings should become native heading blocks.
- Bullet and numbered Markdown rows should become list-item blocks.
- Block quotes should render as normal readable quote/paragraph content, not raw `>` lines.
- Durable image URLs or Markdown image links (`![alt](url)`) should become image blocks.
- Consecutive Markdown table rows must become native BlockNote table blocks.
- If an Agent stores a whole Markdown document inside one paragraph block with embedded newlines, Xiaoduiyou should split and normalize that paragraph into native blocks before rendering.
- Horizontal-rule separator noise such as `---` should be dropped rather than shown as literal document text.

## Native table shape

A Markdown table like:

```markdown
| 指标 | 说明 |
| --- | --- |
| A | 第一项 |
| B | 第二项 |
```

should be represented as:

```json
{
  "type": "table",
  "content": {
    "type": "tableContent",
    "headerRows": 1,
    "rows": [
      { "cells": ["指标", "说明"] },
      { "cells": ["A", "第一项"] },
      { "cells": ["B", "第二项"] }
    ]
  }
}
```

Do not flatten table rows into paragraphs joined by `｜`; that loses source structure and fails visual QA.

## Validation checklist

- Tables are visible as table blocks in the process document.
- Header row is preserved when the Markdown separator row exists.
- The publish tabs still use `publish_notes.<platform>` and do not scrape process material.
- Raw Markdown syntax should only remain when it is intentionally part of the content.
