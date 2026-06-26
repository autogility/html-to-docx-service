const fs = require('fs');
const HTMLtoDOCX = require('html-to-docx');

const [,, inputPath, outputPath] = process.argv;

if (!inputPath || !outputPath) {
  console.error('Usage: node convert.js <input.html> <output.docx>');
  process.exit(1);
}

function cleanHtml(html) {
  // 1. Remove Google Fonts imports
  html = html.replace(/@import\s+url\(['"]?https:\/\/fonts\.googleapis\.com[^)]*\)['"]?\s*;?/gi, '');

  // 2. Replace known CSS variables with values BEFORE anything else
  const cssVars = {
    '--ink':         '#0B1F33',
    '--paper':       '#FAF8F4',
    '--accent':      '#C9622A',
    '--accent-soft': '#F4E3D6',
    '--slate':       '#5B6470',
    '--hairline':    '#D8D3C8',
    '--card':        '#FFFFFF',
    '--danger':      '#B23A2E',
  };
  for (const [k, v] of Object.entries(cssVars)) {
    html = html.replaceAll(`var(${k})`, v);
  }

  // 3. Remove ALL remaining var(--anything) — this is the root cause of @w crash
  html = html.replace(/var\(--[^)]+\)/g, '');

  // 4. Remove draft watermark div
  html = html.replace(/<div[^>]*class="[^"]*draft-watermark[^"]*"[^>]*>.*?<\/div>/gis, '');

  // 5. Replace web fonts
  html = html.replace(/['"]?Source Serif 4['"]?/gi, 'Georgia');
  html = html.replace(/['"]?Inter['"]?/gi, 'Arial');

  // 6. Remove position:fixed
  html = html.replace(/position\s*:\s*fixed/gi, 'position:static');

  // 7. Strip ALL inline styles from table, tr, td, th elements
  // html-to-docx has bugs with complex CSS in table cells — safer to remove
  html = html.replace(/<(table|tr|td|th)([^>]*)\s+style="[^"]*"([^>]*)>/gi, '<$1$2$3>');

  // 8. Strip width attributes that may have garbage values
  html = html.replace(/<(td|th)[^>]*\s+width="[^"]*"([^>]*)>/gi, '<$1$2>');

  // 9. Remove <style> blocks entirely — html-to-docx handles basic tags natively
  // Keeping complex CSS causes more harm than good for DOCX conversion
  html = html.replace(/<style[^>]*>.*?<\/style>/gis, '');

  // 10. Remove script tags
  html = html.replace(/<script[^>]*>.*?<\/script>/gis, '');

  return html;
}

async function convert() {
  try {
    let html = fs.readFileSync(inputPath, 'utf8');
    html = cleanHtml(html);

    console.log(`HTML cleaned: ${html.length} chars`);

    // Verify no var(-- remains
    const remaining = (html.match(/var\(--/g) || []).length;
    console.log(`Remaining var(-- occurrences: ${remaining}`);

    const docxBuffer = await HTMLtoDOCX(html, null, {
      table: { row: { cantSplit: true } },
      footer: false,
      header: false,
      pageNumber: false,
      font: 'Arial',
      fontSize: 22,
      margins: { top: 720, right: 900, bottom: 720, left: 900 },
    });

    fs.writeFileSync(outputPath, docxBuffer);
    console.log(`DOCX written: ${outputPath} (${docxBuffer.length} bytes)`);
    process.exit(0);

  } catch (err) {
    console.error('Conversion error:', err.message);
    console.error(err.stack);
    process.exit(1);
  }
}

convert();
