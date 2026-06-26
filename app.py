import os
import re
import subprocess
import tempfile
import logging
from flask import Flask, request, send_file, jsonify

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def clean_html_for_libreoffice(html: str) -> str:
    """
    Strip things LibreOffice can't handle:
    - Google Fonts @import (network calls fail in sandbox)
    - CSS variables (var(--x) unsupported)
    - Complex CSS selectors LibreOffice ignores anyway
    Replace with safe system font fallbacks.
    """
    # Remove Google Fonts import lines
    html = re.sub(
        r"@import\s+url\(['\"]?https://fonts\.googleapis\.com[^)]*\)['\"]?\s*;?",
        "",
        html,
        flags=re.IGNORECASE
    )

    # Replace CSS custom properties (var(--x)) with safe fallbacks
    # Do this in <style> blocks only
    def replace_vars_in_style(match):
        style = match.group(0)
        # Common var replacements
        replacements = {
            "var(--ink)":          "#0B1F33",
            "var(--paper)":        "#FAF8F4",
            "var(--accent)":       "#C9622A",
            "var(--accent-soft)":  "#F4E3D6",
            "var(--slate)":        "#5B6470",
            "var(--hairline)":     "#D8D3C8",
            "var(--card)":         "#FFFFFF",
            "var(--danger)":       "#B23A2E",
            "var(--p)":            "#0B1F33",
            "var(--s)":            "#5B6470",
            "var(--t)":            "#0B1F33",
            "var(--bg2)":          "#FAF8F4",
            "var(--b)":            "#D8D3C8",
        }
        for var, val in replacements.items():
            style = style.replace(var, val)
        # Remove any remaining unresolved var() calls
        style = re.sub(r'var\(--[^)]+\)', '#333333', style)
        return style

    # Apply var replacement inside <style> tags
    html = re.sub(
        r'<style[^>]*>.*?</style>',
        replace_vars_in_style,
        html,
        flags=re.DOTALL | re.IGNORECASE
    )

    # Replace font-family references to web fonts with system fonts
    html = re.sub(
        r"font-family\s*:\s*['\"]?Source Serif 4['\"]?",
        "font-family: Georgia",
        html, flags=re.IGNORECASE
    )
    html = re.sub(
        r"font-family\s*:\s*['\"]?Inter['\"]?",
        "font-family: Arial",
        html, flags=re.IGNORECASE
    )

    # Remove position:fixed (causes LibreOffice layout issues)
    html = re.sub(
        r'position\s*:\s*fixed\s*;?',
        'position: absolute;',
        html, flags=re.IGNORECASE
    )

    # Remove draft watermark div entirely (position:fixed, z-index:999)
    html = re.sub(
        r'<div[^>]*class=["\'][^"\']*draft-watermark[^"\']*["\'][^>]*>.*?</div>',
        '',
        html, flags=re.DOTALL | re.IGNORECASE
    )

    return html


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "html-to-docx"}), 200


@app.route('/convert/docx', methods=['POST'])
def convert_to_docx():
    try:
        content_type = request.content_type or ''

        if 'application/json' in content_type:
            data     = request.get_json(force=True)
            html     = data.get('html', '')
            filename = data.get('filename', 'document.docx')
        else:
            html     = request.data.decode('utf-8')
            filename = request.headers.get('X-Filename', 'document.docx')

        if not html.strip():
            return jsonify({"error": "No HTML content provided"}), 400

        if not filename.endswith('.docx'):
            filename = filename.replace('.pdf', '').replace('.txt', '')
            filename = filename + '.docx'

        logger.info(f"Converting — filename: {filename}, html size: {len(html)} chars")

        # Clean HTML before passing to LibreOffice
        html_clean = clean_html_for_libreoffice(html)
        logger.info(f"HTML cleaned — new size: {len(html_clean)} chars")

        with tempfile.TemporaryDirectory() as tmpdir:
            html_path = os.path.join(tmpdir, 'input.html')
            docx_path = os.path.join(tmpdir, 'input.docx')

            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_clean)

            # Set HOME so LibreOffice can write its user profile
            env = os.environ.copy()
            env['HOME'] = tmpdir

            result = subprocess.run(
                [
                    'libreoffice',
                    '--headless',
                    '--norestore',
                    '--nofirststartwizard',
                    '--convert-to', 'docx',
                    '--outdir', tmpdir,
                    html_path
                ],
                capture_output=True,
                text=True,
                timeout=90,
                env=env
            )

            logger.info(f"LibreOffice return code: {result.returncode}")
            logger.info(f"LibreOffice stdout: {result.stdout}")
            if result.stderr:
                logger.warning(f"LibreOffice stderr: {result.stderr}")

            if not os.path.exists(docx_path):
                # List what IS in tmpdir for debugging
                files = os.listdir(tmpdir)
                logger.error(f"Expected {docx_path}, found: {files}")
                return jsonify({
                    "error": "Output file not created",
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "files_in_tmpdir": files,
                    "returncode": result.returncode
                }), 500

            size = os.path.getsize(docx_path)
            logger.info(f"DOCX created successfully: {size} bytes")

            return send_file(
                docx_path,
                mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                as_attachment=True,
                download_name=filename
            )

    except subprocess.TimeoutExpired:
        logger.error("LibreOffice timed out after 90s")
        return jsonify({"error": "Conversion timed out"}), 504

    except Exception as e:
        logger.exception("Unexpected error")
        return jsonify({"error": str(e)}), 500


@app.route('/convert/pdf', methods=['POST'])
def convert_to_pdf():
    try:
        content_type = request.content_type or ''
        if 'application/json' in content_type:
            data     = request.get_json(force=True)
            html     = data.get('html', '')
            filename = data.get('filename', 'document.pdf')
        else:
            html     = request.data.decode('utf-8')
            filename = request.headers.get('X-Filename', 'document.pdf')

        if not html.strip():
            return jsonify({"error": "No HTML content"}), 400

        html_clean = clean_html_for_libreoffice(html)

        with tempfile.TemporaryDirectory() as tmpdir:
            html_path = os.path.join(tmpdir, 'input.html')
            pdf_path  = os.path.join(tmpdir, 'input.pdf')

            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_clean)

            env = os.environ.copy()
            env['HOME'] = tmpdir

            result = subprocess.run(
                ['libreoffice', '--headless', '--norestore',
                 '--nofirststartwizard', '--convert-to', 'pdf',
                 '--outdir', tmpdir, html_path],
                capture_output=True, text=True, timeout=90, env=env
            )

            if not os.path.exists(pdf_path):
                return jsonify({"error": "PDF not created", "stderr": result.stderr}), 500

            return send_file(pdf_path, mimetype='application/pdf',
                           as_attachment=True, download_name=filename)

    except Exception as e:
        logger.exception("PDF conversion error")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=False)
