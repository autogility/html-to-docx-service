import os
import subprocess
import tempfile
import logging
from flask import Flask, request, send_file, jsonify

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint — keep-alive ping hits this"""
    return jsonify({"status": "ok", "service": "html-to-docx"}), 200


@app.route('/convert/docx', methods=['POST'])
def convert_to_docx():
    """
    Accepts HTML as raw POST body (text/html)
    OR as JSON: { "html": "...", "filename": "optional.docx" }
    Returns a .docx binary file
    """
    try:
        # ── Get HTML content ──────────────────────────────────────────────
        content_type = request.content_type or ''

        if 'application/json' in content_type:
            data     = request.get_json(force=True)
            html     = data.get('html', '')
            filename = data.get('filename', 'document.docx')
        else:
            # raw text/html body
            html     = request.data.decode('utf-8')
            filename = request.headers.get('X-Filename', 'document.docx')

        if not html.strip():
            return jsonify({"error": "No HTML content provided"}), 400

        if not filename.endswith('.docx'):
            filename = filename.replace('.pdf', '.docx').replace('.txt', '.docx')
            if not filename.endswith('.docx'):
                filename += '.docx'

        logger.info(f"Converting HTML to DOCX — filename: {filename}, html length: {len(html)}")

        # ── Write HTML to temp file ───────────────────────────────────────
        with tempfile.TemporaryDirectory() as tmpdir:
            html_path  = os.path.join(tmpdir, 'input.html')
            docx_path  = os.path.join(tmpdir, 'input.docx')

            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html)

            # ── Run LibreOffice conversion ────────────────────────────────
            result = subprocess.run(
                [
                    'libreoffice',
                    '--headless',
                    '--norestore',
                    '--convert-to', 'docx',
                    '--outdir', tmpdir,
                    html_path
                ],
                capture_output=True,
                text=True,
                timeout=90
            )

            logger.info(f"LibreOffice stdout: {result.stdout}")
            if result.returncode != 0:
                logger.error(f"LibreOffice stderr: {result.stderr}")
                return jsonify({
                    "error": "LibreOffice conversion failed",
                    "details": result.stderr
                }), 500

            if not os.path.exists(docx_path):
                logger.error("DOCX output file not found after conversion")
                return jsonify({"error": "Output file not created"}), 500

            logger.info(f"DOCX created: {os.path.getsize(docx_path)} bytes")

            return send_file(
                docx_path,
                mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                as_attachment=True,
                download_name=filename
            )

    except subprocess.TimeoutExpired:
        logger.error("LibreOffice conversion timed out")
        return jsonify({"error": "Conversion timed out (90s limit)"}), 504

    except Exception as e:
        logger.exception("Unexpected error during conversion")
        return jsonify({"error": str(e)}), 500


@app.route('/convert/pdf', methods=['POST'])
def convert_to_pdf():
    """
    Bonus endpoint — also converts HTML → PDF via LibreOffice
    Same input format as /convert/docx
    """
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
            return jsonify({"error": "No HTML content provided"}), 400

        with tempfile.TemporaryDirectory() as tmpdir:
            html_path = os.path.join(tmpdir, 'input.html')
            pdf_path  = os.path.join(tmpdir, 'input.pdf')

            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html)

            result = subprocess.run(
                [
                    'libreoffice',
                    '--headless',
                    '--norestore',
                    '--convert-to', 'pdf',
                    '--outdir', tmpdir,
                    html_path
                ],
                capture_output=True,
                text=True,
                timeout=90
            )

            if result.returncode != 0:
                return jsonify({
                    "error": "LibreOffice conversion failed",
                    "details": result.stderr
                }), 500

            return send_file(
                pdf_path,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=filename
            )

    except Exception as e:
        logger.exception("PDF conversion error")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=False)
