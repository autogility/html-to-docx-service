const fs = require('fs');
const path = require('path');
const HTMLtoDOCX = require('html-to-docx');

const [,, inputPath, outputPath] = process.argv;

if (!inputPath || !outputPath) {
  console.error('Usage: node convert.js <input.html> <output.docx>');
  process.exit(1);
}

async function convert() {
  try {
    let html = fs.readFileSync(inputPath, 'utf8');

    // Strip Google Fonts imports (network not available)
    html = html.replace(/@import\s+url\(['"]?https:\/\/fonts\.googleapis\.com[^)]*\)['"]?\s*;?/gi, '');

    // Replace CSS variables with actual values for the proposal template
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
    for (const [varName, value] of Object.entries(cssVars)) {
      html = html.replaceAll(`var(${varName})`, value);
    }
    // Remove any remaining unresolved CSS vars
    html = html.replace(/var\(--[^)]+\)/g, '#333333');

    // Remove draft watermark (position:fixed causes issues)
    html = html.replace(/<div[^>]*class="[^"]*draft-watermark[^"]*"[^>]*>.*?<\/div>/gis, '');

    // Replace web fonts with system fonts
    html = html.replace(/font-family\s*:\s*['"]?Source Serif 4['"]?/gi, 'font-family: Georgia');
    html = html.replace(/font-family\s*:\s*['"]?Inter['"]?/gi, 'font-family: Arial');

    console.log(`HTML prepared: ${html.length} chars`);

    // Convert using html-to-docx
    const docxBuffer = await HTMLtoDOCX(html, null, {
      table: { row: { cantSplit: true } },
      footer: false,
      header: false,
      pageNumber: false,
      font: 'Arial',
      fontSize: 24,
      margins: {
        top: 720,
        right: 720,
        bottom: 720,
        left: 720,
      },
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
